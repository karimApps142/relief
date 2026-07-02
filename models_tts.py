"""
models_tts.py — Text-to-Speech model wrappers (Hindi / Urdu / English).

Two engines, one per capability, both lazy + cached (like models.py). On a small
GPU we keep only ONE resident at a time — synthesize_* frees the other engine + any
relief/depth models first, so peak VRAM ≈ the single heaviest model.

  • Indic Parler-TTS  (ai4bharat/indic-parler-tts, Apache-2.0)
      Voice DESIGN (describe a voice in words) + named PRESET speakers.
      20 Indic languages incl. Hindi + Urdu, + English. No reference-audio cloning.
  • Chatterbox Multilingual  (ResembleAI/chatterbox, MIT)
      Zero-shot voice CLONING from a ~10 s reference clip. 23 languages incl. Hindi
      + English (NO Urdu — callers must route Urdu to the design engine).

GPU box only — imported lazily by features/text_to_speech.py inside run(), never on
the Mac. Needs the TTS deps documented in requirements-gpu.txt.

Urdu voice CLONING has no reliable open local model today; Higgs-Audio-v3
(bosonai/higgs-audio-v3-tts-4b, non-commercial) is the upgrade path — wire a
synthesize_clone_higgs() branch here once its package is verified on the box.
"""
import functools
import gc

import numpy as np
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# language hint -> Chatterbox ISO code (Chatterbox has no Urdu)
CLONE_LANGS = {"hi": "hi", "en": "en", "auto": "en"}
_LANG_NAME = {"hi": "Hindi", "ur": "Urdu", "en": "English", "auto": ""}


# ---------- engine A: Indic Parler-TTS (voice design + preset speakers) ----------
@functools.lru_cache(maxsize=1)
def _parler():
    try:
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
    except ImportError as e:  # keep the base app unaffected; guide the one-time install
        raise RuntimeError(
            "Indic Parler-TTS is not installed. On the GPU box run:\n"
            "  pip install --no-deps git+https://github.com/huggingface/parler-tts.git\n"
            "  pip install sentencepiece protobuf soundfile descript-audio-codec"
        ) from e
    repo = "ai4bharat/indic-parler-tts"
    model = ParlerTTSForConditionalGeneration.from_pretrained(repo).to(DEVICE).eval()
    tok = AutoTokenizer.from_pretrained(repo)                          # tokenizes the spoken text
    desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)  # the caption
    return model, tok, desc_tok


def synthesize_design(text: str, description: str, seed: int = 0):
    """Voice design / preset: `description` (a natural-language caption of the voice)
    steers gender/pitch/pace/emotion/recording; `text` is what gets spoken. The input
    script (Devanagari vs Nastaʿlīq) selects Hindi vs Urdu. Returns (float32 mono, sr)."""
    _free_other("parler")
    model, tok, desc_tok = _parler()
    if seed:
        torch.manual_seed(int(seed))
    desc = desc_tok(description, return_tensors="pt").to(DEVICE)
    prompt = tok(text, return_tensors="pt").to(DEVICE)
    with torch.inference_mode():
        gen = model.generate(
            input_ids=desc.input_ids, attention_mask=desc.attention_mask,
            prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask,
        )
    audio = gen.to(torch.float32).cpu().numpy().squeeze()
    return audio, int(model.config.sampling_rate)


# ---------- engine B: Chatterbox Multilingual (zero-shot voice cloning) ----------
@functools.lru_cache(maxsize=1)
def _chatterbox():
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except ImportError as e:
        raise RuntimeError(
            "Chatterbox Multilingual is not installed. On the GPU box run:\n"
            "  pip install --no-deps chatterbox-tts\n"
            "  pip install resemble-perth s3tokenizer conformer librosa omegaconf"
        ) from e
    return ChatterboxMultilingualTTS.from_pretrained(device=DEVICE)


def synthesize_clone(text: str, ref_wav: str, language_id: str,
                     exaggeration: float = 0.5, cfg_weight: float = 0.5, seed: int = 0):
    """Zero-shot clone: speak `text` in `language_id` (hi/en) using the timbre of the
    speaker in `ref_wav` (a clean ~10 s clip). Returns (float32 mono, sr)."""
    _free_other("chatterbox")
    model = _chatterbox()
    if seed:
        torch.manual_seed(int(seed))
    kwargs = {"language_id": language_id, "audio_prompt_path": ref_wav,
              "exaggeration": float(exaggeration), "cfg_weight": float(cfg_weight)}
    try:
        wav = model.generate(text, **kwargs)
    except TypeError:  # older/newer signature without the emotion knobs
        wav = model.generate(text, language_id=language_id, audio_prompt_path=ref_wav)
    t = wav.detach().to(torch.float32).cpu()
    audio = t.squeeze().numpy()
    sr = int(getattr(model, "sr", 24000))
    return audio, sr


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


def _free_other(keep: str):
    """Drop the TTS engine we're NOT about to use + any relief/depth models, so a small
    GPU only ever holds one heavy model. Best-effort; harmless if nothing is loaded."""
    (_chatterbox if keep == "parler" else _parler).cache_clear()
    try:
        import models
        models.unload_all()
    except Exception:
        pass
    _empty_cache()


def unload_tts():
    """Free both TTS engines + VRAM (e.g. before a heavy image/relief run)."""
    _parler.cache_clear()
    _chatterbox.cache_clear()
    _empty_cache()
