"""
models_tts.py — Text-to-Speech model wrappers (Hindi / Urdu / English).

Primary engine is **MMS-TTS** (Meta), which ships INSIDE `transformers` (VitsModel) —
so it runs on the box's existing modern stack with no conflicting installs. It gives
one clean, fixed voice per language (no cloning / no design), but it works today.

Optional UPGRADES (voice design / cloning) need their own pinned deps that clash with
the box's transformers/torch, so they can only run isolated (separate venv + subprocess,
not yet wired). We still TRY them per call and fall back to MMS if they can't import, so
the moment an isolated path exists they light up automatically:
  • Indic Parler-TTS  — voice DESIGN + presets  (transformers==4.46 → conflicts in-venv)
  • Chatterbox Multilingual — zero-shot CLONING  (torch==2.6 → conflicts in-venv)

GPU box only — imported lazily by features/text_to_speech.py inside run(), never on the Mac.
"""
import functools
import gc

import numpy as np
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# language hint -> Chatterbox ISO code (Chatterbox has no Urdu)
CLONE_LANGS = {"hi": "hi", "en": "en", "auto": "en"}
_LANG_NAME = {"hi": "Hindi", "ur": "Urdu", "en": "English", "auto": ""}

# language -> MMS-TTS repo (VitsModel, bundled in transformers). Urdu uses the
# Arabic-script (Nastaʿlīq) model to match what users type.
_MMS_REPO = {"hi": "facebook/mms-tts-hin",
             "ur": "facebook/mms-tts-urd-script_arabic",
             "en": "facebook/mms-tts-eng",
             "auto": "facebook/mms-tts-hin"}

# remembers whether the heavy optional engines actually import here, so we don't
# re-attempt (and re-log) a guaranteed ImportError on every request.
_engine_ok = {"parler": None, "chatterbox": None}


# ---------- primary engine: MMS-TTS (bundled in transformers — always works) ----------
@functools.lru_cache(maxsize=3)
def _mms(repo):
    from transformers import VitsModel, AutoTokenizer
    model = VitsModel.from_pretrained(repo).to(DEVICE).eval()
    tok = AutoTokenizer.from_pretrained(repo)
    return model, tok


@functools.lru_cache(maxsize=1)
def _uroman():
    """uroman romanizer (only needed by some MMS languages, e.g. Urdu/Arabic script)."""
    import uroman as _ur
    return _ur.Uroman()


def _uromanize(text):
    try:
        return _uroman().romanize_string(text)
    except ModuleNotFoundError as e:
        raise RuntimeError("This language's MMS voice needs romanization. On the box run:\n"
                           "  pip install uroman") from e
    except AttributeError:
        import uroman as _ur                       # tolerate older/alt package API
        return _ur.uroman(text)


def synthesize_mms(text, language="hi"):
    """One fixed MMS voice for the language. Returns (float32 mono, sr=16 kHz)."""
    repo = _MMS_REPO.get(language, _MMS_REPO["hi"])
    model, tok = _mms(repo)
    if getattr(tok, "is_uroman", False):           # Arabic/Nastaʿlīq etc. → romanize first
        text = _uromanize(text)
    inputs = tok(text, return_tensors="pt").to(DEVICE)
    with torch.inference_mode():
        wav = model(**inputs).waveform             # (1, N)
    audio = wav.squeeze().to(torch.float32).cpu().numpy()
    return audio, int(model.config.sampling_rate)


# ---------- optional upgrade A: Indic Parler-TTS (voice design + presets) ----------
@functools.lru_cache(maxsize=1)
def _parler():
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer
    repo = "ai4bharat/indic-parler-tts"
    model = ParlerTTSForConditionalGeneration.from_pretrained(repo).to(DEVICE).eval()
    tok = AutoTokenizer.from_pretrained(repo)
    desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    return model, tok, desc_tok


def _parler_generate(text, description, seed=0):
    model, tok, desc_tok = _parler()
    if seed:
        torch.manual_seed(int(seed))
    desc = desc_tok(description, return_tensors="pt").to(DEVICE)
    prompt = tok(text, return_tensors="pt").to(DEVICE)
    with torch.inference_mode():
        gen = model.generate(
            input_ids=desc.input_ids, attention_mask=desc.attention_mask,
            prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask)
    audio = gen.to(torch.float32).cpu().numpy().squeeze()
    return audio, int(model.config.sampling_rate)


def synthesize_design(text, description, language="hi", seed=0):
    """Voice design / preset. Uses Indic Parler-TTS if it can load in this env; otherwise
    falls back to the always-available MMS voice for the language."""
    if _engine_ok["parler"] is not False:
        try:
            _free_other("parler")
            out = _parler_generate(text, description, seed)
            _engine_ok["parler"] = True
            return out
        except Exception as e:
            _engine_ok["parler"] = False
            print(f"[tts] Parler-TTS unavailable here ({type(e).__name__}) — using MMS-TTS. "
                  "Voice design needs the isolated Parler venv.")
    return synthesize_mms(text, language)


# ---------- optional upgrade B: Chatterbox Multilingual (zero-shot cloning) ----------
@functools.lru_cache(maxsize=1)
def _chatterbox():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    return ChatterboxMultilingualTTS.from_pretrained(device=DEVICE)


def synthesize_clone(text, ref_wav, language_id, exaggeration=0.5, cfg_weight=0.5, seed=0):
    """Zero-shot clone via Chatterbox. Raises a clear message if it can't run in this env
    (MMS can't clone — cloning needs the isolated Chatterbox setup)."""
    if _engine_ok["chatterbox"] is False:
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
        _engine_ok["chatterbox"] = True
        audio = wav.detach().to(torch.float32).cpu().squeeze().numpy()
        return audio, int(getattr(model, "sr", 24000))
    except RuntimeError:
        raise
    except Exception as e:
        _engine_ok["chatterbox"] = False
        raise RuntimeError(f"{_CLONE_UNAVAILABLE}\n[{type(e).__name__}: {e}]") from e


_CLONE_UNAVAILABLE = (
    "Voice cloning isn't available in this environment yet — Chatterbox needs its own "
    "pinned deps (torch 2.6 / numpy<2) that conflict with the box, so it must run in an "
    "isolated venv (not wired up yet). Design & Preset work now via MMS-TTS; for Urdu, "
    "use Voice design.")


# ---------- shared helpers ----------
def write_wav(path, audio, sr):
    """Write a float32 mono waveform to a 16-bit WAV (soundfile, torchaudio fallback)."""
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
    """Drop the engines we're NOT about to use + any relief/depth models, so a small GPU
    only ever holds one heavy model. Best-effort; harmless if nothing is loaded."""
    if keep != "chatterbox":
        _chatterbox.cache_clear()
    if keep != "parler":
        _parler.cache_clear()
    try:
        import models
        models.unload_all()
    except Exception:
        pass
    _empty_cache()


def unload_tts():
    """Free all TTS engines + VRAM (e.g. before a heavy image/relief run)."""
    _mms.cache_clear()
    _parler.cache_clear()
    _chatterbox.cache_clear()
    _empty_cache()
