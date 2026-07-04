"""features/text_to_speech.py — Hindi / Urdu / English speech from text.

Three modes behind one panel, dispatched to the right engine (see models_tts):
  • Voice design  — invent a voice from a written description (Indic Parler-TTS)
  • Preset voice  — a named, reproducible Indic Parler speaker
  • Voice cloning — copy a voice from an uploaded ~10 s sample (Chatterbox, hi/en)

`inputs = ["audio"]` gives the panel an OPTIONAL reference-clip uploader (only used by
cloning) without gating Generate — the server keys the upload as inputs["audio"]. Heavy
libs are imported lazily inside run(), so the module stays Mac-import-safe.
"""
from pathlib import Path

from .base import Feature, ParamSpec

_LANG_NAME = {"hi": "Hindi", "ur": "Urdu", "en": "English", "auto": ""}
_CLONE_LANGS = {"hi": "hi", "en": "en", "auto": "en"}      # Chatterbox has no Urdu


def _description(mode, params, language):
    """Build the Indic Parler-TTS caption that steers the voice (design + preset)."""
    if mode == "preset":
        base = f"{params.get('speaker') or 'Divya'}'s voice is clear and expressive"
    else:
        base = (params.get("voice_description") or "").strip() \
            or "A clear, natural, expressive voice with a neutral tone"
    speed = float(params.get("speed") or 1.0)
    rate = "at a slow pace" if speed < 0.9 else "at a fast pace" if speed > 1.1 else "at a moderate pace"
    parts = [base, rate]
    lang = _LANG_NAME.get(language, "")
    if lang:
        parts.append(f"speaking in {lang}")
    parts.append("recorded very close-up with excellent audio quality and almost no background noise")
    return ", ".join(parts) + "."


class TextToSpeechFeature(Feature):
    id = "text2speech"
    name = "Text → Speech"
    description = "Hindi / Urdu / English speech — design a voice, use a preset, or clone from a sample."
    inputs = ["audio"]                 # optional reference clip (cloning); does NOT gate Generate
    engine = "local"
    needs_comfy = False
    icon = "speech"
    est_runtime = "~2–15 s"
    vram = "~0.5–2 GB"
    output_kinds = ["Speech WAV"]
    guide = [
        {"h": "Engine",
         "b": "Runs on MMS-TTS (Meta), bundled in transformers — Hindi, Urdu & English work "
              "today with one clean fixed voice per language. Type in Devanagari (Hindi) or "
              "Nastaʿlīq (Urdu); the script sets the language."},
        {"h": "Voice design & presets",
         "b": "The description / preset controls become active once the isolated Indic Parler-TTS "
              "engine is set up (its deps conflict with this box's transformers, so it can't run "
              "in-process). Until then all modes use the MMS voice."},
        {"h": "Voice cloning",
         "b": "Cloning needs the isolated Chatterbox engine (torch 2.6 / numpy<2 — conflicts here), "
              "so it's not active yet. Hindi & English only when enabled; Urdu has no open cloner."},
        {"h": "Urdu note",
         "b": "The Urdu MMS voice may need a one-time 'pip install uroman' on the box (romanizer). "
              "If a run reports it, install that and retry."},
    ]
    params = [
        ParamSpec("text", "text", "", "Text",
                  placeholder="Type Hindi, Urdu, or English text to speak…"),
        ParamSpec("mode", "select", "design", "Mode", control="seg",
                  help="Design = invent a voice · Clone = copy a sampled voice · Preset = a named voice.",
                  choices=[{"value": "design", "label": "Voice design"},
                           {"value": "clone", "label": "Voice cloning"},
                           {"value": "preset", "label": "Preset voice"}]),
        ParamSpec("language", "select", "hi", "Language", control="seg",
                  help="Hindi & Urdu are the focus. Cloning supports Hindi/English (use Design for Urdu).",
                  choices=[{"value": "hi", "label": "Hindi"}, {"value": "ur", "label": "Urdu"},
                           {"value": "en", "label": "English"}, {"value": "auto", "label": "Auto"}]),
        ParamSpec("voice_description", "text", "", "Voice description",
                  depends_on={"param": "mode", "value": "design"},
                  placeholder="A warm, calm female voice, clear and expressive, close-up studio recording.",
                  help="Describe the voice: gender, age, pitch, pace, emotion, recording feel. "
                       "Indic Parler-TTS turns this into a voice."),
        ParamSpec("speaker", "select", "Divya", "Preset voice",
                  depends_on={"param": "mode", "value": "preset"},
                  help="Named Indic Parler voices — most reliable for Hindi. For Urdu, prefer Voice design.",
                  choices=[{"value": "Divya", "label": "Divya (f)"}, {"value": "Rohit", "label": "Rohit (m)"},
                           {"value": "Aman", "label": "Aman (m)"}, {"value": "Rani", "label": "Rani (f)"},
                           {"value": "Sunita", "label": "Sunita (f)"}, {"value": "Karan", "label": "Karan (m)"}]),
        ParamSpec("speed", "number", 1.0, "Speed", 0.7, 1.3, 0.05, control="slider", suffix="×",
                  group="advanced", help="Speaking pace for Design / Preset (mapped into the voice description)."),
        ParamSpec("exaggeration", "number", 0.5, "Expressiveness", 0.25, 1.0, 0.05, control="slider",
                  group="advanced", depends_on={"param": "mode", "value": "clone"},
                  help="Chatterbox emotion intensity. 0.5 = natural; higher = more dramatic."),
        ParamSpec("cfg_weight", "number", 0.5, "Pace / guidance", 0.2, 1.0, 0.05, control="slider",
                  group="advanced", depends_on={"param": "mode", "value": "clone"},
                  help="Lower = slower, more deliberate delivery; higher = snappier."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper",
                  group="advanced", help="0 = random each run."),
    ]

    def run(self, inputs, params, out_dir):
        import models_tts
        text = (params.get("text") or "").strip()
        if not text:
            raise ValueError("Enter some text to speak.")
        mode = params.get("mode", "design")
        language = params.get("language", "hi")
        seed = int(params.get("seed") or 0)

        if mode == "clone":
            ref = inputs.get("audio") or inputs.get("image")
            if not ref:
                raise ValueError("Voice cloning needs a reference clip — upload a clean ~10 s WAV/MP3, "
                                 "or switch Mode to Voice design.")
            lang = _CLONE_LANGS.get(language)
            if lang is None:
                raise ValueError(f"Voice cloning doesn't support {_LANG_NAME.get(language, language)} yet "
                                 "(Chatterbox has no Urdu). Use Mode = Voice design for Urdu.")
            audio, sr = models_tts.synthesize_clone(
                text, ref, lang,
                exaggeration=params.get("exaggeration", 0.5),
                cfg_weight=params.get("cfg_weight", 0.5), seed=seed)
        else:
            audio, sr = models_tts.synthesize_design(text, _description(mode, params, language),
                                                     language=language, seed=seed)

        out = Path(out_dir) / "speech.wav"
        models_tts.write_wav(out, audio, sr)
        return {"audio": str(out)}
