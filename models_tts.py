"""
models_tts.py — Text-to-Speech via Qwen3-TTS (Alibaba Qwen, open weights).

One model family, three capabilities — each a SEPARATE checkpoint (all 1.7B, bf16):
  • design → generate_voice_design(text, language, instruct)              [VoiceDesign]
  • preset → generate_custom_voice(text, language, speaker)               [CustomVoice]
  • clone  → generate_voice_clone(text, language, ref_audio, ref_text)    [Base]

`qwen-tts` is a 2026 release with loose deps, so it runs IN-PROCESS on the box's modern
stack (transformers 5.x / torch 2.5+cu121 / numpy 2) — no isolated venv. Lazy + cached
with only ONE checkpoint resident at a time (relief/depth models are freed first) so it
fits a 12 GB GPU. GPU box only — imported lazily inside the feature's run(), never the Mac.
"""
import functools
import gc

import numpy as np
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

# valid `language` strings and CustomVoice `speaker` names (from the model cards)
LANGUAGES = ["English", "Chinese", "Japanese", "Korean", "German",
             "French", "Russian", "Portuguese", "Spanish", "Italian"]
SPEAKERS = ["Ryan", "Aiden", "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ono_Anna", "Sohee"]

_REPO = {"design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
         "preset": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
         "clone":  "Qwen/Qwen3-TTS-12Hz-1.7B-Base"}

_current = [None]                                          # which checkpoint is resident


@functools.lru_cache(maxsize=1)
def _model(kind):
    try:
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        raise RuntimeError("Qwen3-TTS is not installed. On the GPU box run:\n"
                           "  pip install -U qwen-tts") from e
    dev = "cuda:0" if DEVICE == "cuda" else "cpu"
    return Qwen3TTSModel.from_pretrained(_REPO[kind], device_map=dev, dtype=_DTYPE)


def _load(kind):
    """Load a Qwen3-TTS checkpoint, keeping only ONE resident (small-GPU friendly)."""
    if _current[0] not in (None, kind):
        _model.cache_clear()                              # drop the previous checkpoint
        _empty_cache()
    _mms.cache_clear()                                    # free the MMS engine if it was resident
    _current[0] = kind
    try:                                                  # free relief/depth VRAM for the TTS model
        import models
        models.unload_all()
    except Exception:
        pass
    return _model(kind)


def _wave(wavs):
    """Qwen returns (wavs, sr) with wavs a list; take the first as float32 mono."""
    w = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
    if hasattr(w, "detach"):
        w = w.detach().to(torch.float32).cpu().numpy()
    return np.asarray(w, dtype=np.float32).squeeze()


def synthesize_design(text, instruct, language="English", seed=0):
    """Voice DESIGN — the natural-language `instruct` invents/controls the voice."""
    if seed:
        torch.manual_seed(int(seed))
    m = _load("design")
    wavs, sr = m.generate_voice_design(text=text, language=language, instruct=instruct)
    return _wave(wavs), int(sr)


def synthesize_preset(text, speaker, language="English", seed=0):
    """PRESET voice — one of the 9 built-in Qwen speakers."""
    if seed:
        torch.manual_seed(int(seed))
    m = _load("preset")
    wavs, sr = m.generate_custom_voice(text=text, language=language, speaker=speaker)
    return _wave(wavs), int(sr)


def synthesize_clone(text, ref_audio, ref_text="", language="English", seed=0):
    """Voice CLONING — mimic the speaker in `ref_audio` (ref_text = its transcript, optional)."""
    if seed:
        torch.manual_seed(int(seed))
    m = _load("clone")
    wavs, sr = m.generate_voice_clone(text=text, language=language,
                                      ref_audio=ref_audio, ref_text=ref_text or "")
    return _wave(wavs), int(sr)


# ---------- Hindi / Urdu via MMS-TTS (Qwen3-TTS has no Hindi/Urdu) ----------
# MMS ships inside transformers (VitsModel), so it runs in-process too — one fixed voice per
# language, no design/cloning, but real Hindi/Urdu. Used only when the user picks Hindi/Urdu.
_MMS_REPO = {"hi": "facebook/mms-tts-hin",
             "ur": "facebook/mms-tts-urd-script_arabic",
             "en": "facebook/mms-tts-eng"}
_MMS_NAME = {"hi": "Hindi", "ur": "Urdu", "en": "English"}


@functools.lru_cache(maxsize=2)
def _mms(repo):
    from transformers import VitsModel, AutoTokenizer
    model = VitsModel.from_pretrained(repo).to(DEVICE).eval()
    return model, AutoTokenizer.from_pretrained(repo)


@functools.lru_cache(maxsize=1)
def _uroman():
    import uroman as _ur
    return _ur.Uroman()


def _uromanize(text):
    try:
        return _uroman().romanize_string(text)
    except ModuleNotFoundError as e:
        raise RuntimeError("Urdu needs a romanizer. On the box run:  pip install uroman") from e
    except AttributeError:
        import uroman as _ur
        return _ur.uroman(text)


def synthesize_mms(text, lang_code):
    """One fixed MMS voice for Hindi / Urdu / English. Returns (float32 mono, 16 kHz)."""
    _model.cache_clear()                                  # drop any resident Qwen checkpoint
    _current[0] = None
    try:
        import models
        models.unload_all()
    except Exception:
        pass
    _empty_cache()
    model, tok = _mms(_MMS_REPO.get(lang_code, _MMS_REPO["hi"]))
    src = _uromanize(text) if getattr(tok, "is_uroman", False) else text
    inputs = tok(src, return_tensors="pt")
    if inputs["input_ids"].numel() == 0:                  # empty tokenization would crash VITS
        raise ValueError(f"That text has no {_MMS_NAME.get(lang_code, lang_code)} characters to "
                         "speak — type it in the right script (Devanagari for Hindi, Nastaʿlīq for Urdu).")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.inference_mode():
        wav = model(**inputs).waveform
    return wav.squeeze().to(torch.float32).cpu().numpy(), int(model.config.sampling_rate)


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


def unload_tts():
    """Free the resident TTS checkpoint(s) + VRAM (e.g. before a heavy relief run)."""
    _model.cache_clear()
    _mms.cache_clear()
    _current[0] = None
    _empty_cache()
