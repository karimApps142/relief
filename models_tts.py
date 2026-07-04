"""
models_tts.py — Text-to-Speech engine dispatch (Hindi / Urdu / English).

The box runs a modern stack (transformers 5.12, numpy 2, torch 2.5+cu121). The good
design/cloning models pin OLD, mutually-incompatible deps, so they can't import here.
Strategy:

  • MMS-TTS (Meta VITS, bundled in transformers) is the always-works engine — one fixed
    voice per language. We reshape it with Speed (VITS speaking_rate) + Pitch (librosa
    pitch-shift) so the controls actually change the output.
  • Real voice DESIGN (description → gender/pitch/pace/emotion) uses Indic Parler-TTS in
    an ISOLATED venv (.venv-tts) driven as a subprocess (tts_worker.py). When that venv
    exists we route Design through it automatically; otherwise we fall back to MMS+knobs.
  • Voice CLONING (Chatterbox) is attempted in-process and reports a clear message if its
    deps can't run here (a second isolated venv is the eventual home).

GPU box only — imported lazily by features/text_to_speech.py inside run(), never on the Mac.
"""
import functools
import gc
import os
from pathlib import Path

import numpy as np
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

CLONE_LANGS = {"hi": "hi", "en": "en", "auto": "en"}       # Chatterbox has no Urdu
_LANG_NAME = {"hi": "Hindi", "ur": "Urdu", "en": "English", "auto": ""}
_MMS_REPO = {"hi": "facebook/mms-tts-hin",
             "ur": "facebook/mms-tts-urd-script_arabic",
             "en": "facebook/mms-tts-eng",
             "auto": "facebook/mms-tts-hin"}

_chatterbox_ok = [None]                                    # cache in-process clone availability
_worker_missing = [False]                                  # cache "no .venv-tts" so we don't re-check


# ---------- primary engine: MMS-TTS (bundled in transformers — always works) ----------
@functools.lru_cache(maxsize=3)
def _mms(repo):
    from transformers import VitsModel, AutoTokenizer
    model = VitsModel.from_pretrained(repo).to(DEVICE).eval()
    tok = AutoTokenizer.from_pretrained(repo)
    return model, tok


@functools.lru_cache(maxsize=1)
def _uroman():
    import uroman as _ur
    return _ur.Uroman()


def _uromanize(text):
    try:
        return _uroman().romanize_string(text)
    except ModuleNotFoundError as e:
        raise RuntimeError("This language's MMS voice needs romanization. On the box run:\n"
                           "  pip install uroman") from e
    except AttributeError:
        import uroman as _ur
        return _ur.uroman(text)


def _detect_lang(text):
    """Pick the MMS model by the SCRIPT typed — MMS voices are script-locked."""
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:
            return "hi"                                    # Devanagari → Hindi
        if (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F
                or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF):
            return "ur"                                    # Arabic/Nastaʿlīq → Urdu
    return "en"                                            # Latin / other → English


def _pitch_shift(audio, sr, semitones):
    if not semitones or abs(float(semitones)) < 1e-3:
        return audio
    try:
        import librosa
        return librosa.effects.pitch_shift(np.asarray(audio, np.float32), sr=int(sr),
                                           n_steps=float(semitones)).astype(np.float32)
    except Exception as e:
        print(f"[tts] pitch shift skipped ({type(e).__name__}: {e})")
        return audio


def synthesize_mms(text, language="hi", speed=1.0, pitch=0.0):
    """MMS voice for the typed script, reshaped by speed (speaking_rate) + pitch (semitones).
    Returns (float32 mono, sr)."""
    lang = _detect_lang(text)
    if language not in ("auto", lang):
        print(f"[tts] text looks like {_LANG_NAME.get(lang, lang)}; using that MMS voice "
              f"(Language was {_LANG_NAME.get(language, language)}).")
    model, tok = _mms(_MMS_REPO[lang])
    src = _uromanize(text) if getattr(tok, "is_uroman", False) else text
    inputs = tok(src, return_tensors="pt")
    if inputs["input_ids"].numel() == 0:
        raise ValueError(
            f"That text has no {_LANG_NAME.get(lang, lang)} characters to speak. Type it in the "
            "right script — Devanagari for Hindi, Nastaʿlīq for Urdu, Latin for English.")
    try:                                                   # Speed → VITS speaking_rate (higher = faster)
        model.speaking_rate = float(speed or 1.0)
    except Exception:
        pass
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.inference_mode():
        wav = model(**inputs).waveform                     # (1, N)
    audio = wav.squeeze().to(torch.float32).cpu().numpy()
    sr = int(model.config.sampling_rate)
    audio = _pitch_shift(audio, sr, pitch)                 # Pitch → librosa shift
    return audio, sr


# ---------- isolated voice-DESIGN engine: Indic Parler-TTS via subprocess ----------
def _tts_venv_python():
    """Interpreter of the isolated TTS venv, or None. Override with env TTS_VENV_PY."""
    override = os.environ.get("TTS_VENV_PY")
    if override:
        return override if Path(override).exists() else None
    base = Path(__file__).resolve().parent / ".venv-tts"
    cand = base / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(cand) if cand.exists() else None


def _read_wav(path):
    try:
        import soundfile as sf
        a, sr = sf.read(path, dtype="float32")
        return (a.mean(axis=1) if a.ndim > 1 else a), int(sr)
    except Exception:
        import wave
        with wave.open(path, "rb") as w:
            sr, n = w.getframerate(), w.getnframes()
            raw = w.readframes(n)
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, int(sr)


def _run_design_worker(text, description, language, seed):
    """Run Indic Parler-TTS in the isolated venv. Returns (audio, sr) or None if no venv."""
    py = _tts_venv_python()
    if not py:
        _worker_missing[0] = True
        return None
    import subprocess, tempfile, json
    try:                                                   # free main-process VRAM for the worker
        import models
        models.unload_all()
    except Exception:
        pass
    _empty_cache()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    req = {"mode": "design", "text": text, "description": description,
           "language": language, "seed": int(seed or 0), "out": tmp}
    worker = str(Path(__file__).resolve().parent / "tts_worker.py")
    proc = subprocess.run([py, worker], input=json.dumps(req),
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError("Parler worker: " + (proc.stderr or proc.stdout or "failed")[-500:])
    audio, sr = _read_wav(tmp)
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return audio, sr


def synthesize_design(text, description, language="hi", seed=0, speed=1.0, pitch=0.0):
    """Real voice design via the isolated Parler venv when present; otherwise the MMS voice
    reshaped by the Speed + Pitch knobs."""
    if not _worker_missing[0]:
        try:
            res = _run_design_worker(text, description, language, seed)
            if res is not None:
                return res
        except Exception as e:
            print(f"[tts] Parler design worker failed ({type(e).__name__}: {e}) — using MMS.")
    return synthesize_mms(text, language, speed=speed, pitch=pitch)


# ---------- voice CLONING: Chatterbox (in-process attempt) ----------
@functools.lru_cache(maxsize=1)
def _chatterbox():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    return ChatterboxMultilingualTTS.from_pretrained(device=DEVICE)


_CLONE_UNAVAILABLE = (
    "Voice cloning isn't available in this environment yet — Chatterbox needs its own pinned "
    "deps (torch 2.6 / numpy<2) that conflict with the box, so it must run in an isolated venv "
    "(not wired up yet). Design & Preset work now; for Urdu use Voice design.")


def synthesize_clone(text, ref_wav, language_id, exaggeration=0.5, cfg_weight=0.5, seed=0):
    if _chatterbox_ok[0] is False:
        raise RuntimeError(_CLONE_UNAVAILABLE)
    try:
        _free_other("chatterbox")
        model = _chatterbox()
        if seed:
            torch.manual_seed(int(seed))
        kwargs = {"language_id": language_id, "audio_prompt_path": ref_wav,
                  "exaggeration": float(exaggeration), "cfg_weight": float(cfg_weight)}
        try:
            wav = model.generate(text, **kwargs)
        except TypeError:
            wav = model.generate(text, language_id=language_id, audio_prompt_path=ref_wav)
        _chatterbox_ok[0] = True
        audio = wav.detach().to(torch.float32).cpu().squeeze().numpy()
        return audio, int(getattr(model, "sr", 24000))
    except Exception as e:
        _chatterbox_ok[0] = False
        raise RuntimeError(f"{_CLONE_UNAVAILABLE}\n[{type(e).__name__}: {e}]") from e


# ---------- shared helpers ----------
def write_wav(path, audio, sr):
    audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    try:
        import soundfile as sf
        sf.write(str(path), audio, int(sr))
    except Exception:
        import torchaudio
        torchaudio.save(str(path), torch.from_numpy(audio).unsqueeze(0), int(sr))


def _empty_cache():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _free_other(keep):
    if keep != "chatterbox":
        _chatterbox.cache_clear()
    try:
        import models
        models.unload_all()
    except Exception:
        pass
    _empty_cache()


def unload_tts():
    _mms.cache_clear()
    _chatterbox.cache_clear()
    _empty_cache()
