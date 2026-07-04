"""features/text_to_speech.py — speech from text via Qwen3-TTS (open weights, in-process).

Three modes, each mapped to a Qwen3-TTS checkpoint (see models_tts):
  • Voice design  — describe a voice in words → generate_voice_design (VoiceDesign)
  • Preset voice  — one of 9 built-in Qwen speakers → generate_custom_voice (CustomVoice)
  • Voice cloning — copy a voice from an uploaded clip → generate_voice_clone (Base)

`inputs = ["audio"]` gives the panel an optional reference-clip uploader (cloning only)
without gating Generate; the server keys the upload as inputs["audio"]. qwen-tts is
imported lazily inside run(), so the module stays Mac-import-safe.
"""
from pathlib import Path

from .base import Feature, ParamSpec

# Qwen3-TTS's 10 languages (full design/cloning) + Hindi/Urdu routed to MMS (basic voice).
_QWEN_LANGUAGES = ["English", "Chinese", "Japanese", "Korean", "German",
                   "French", "Russian", "Portuguese", "Spanish", "Italian"]
_MMS_LANGUAGES = ["Hindi", "Urdu"]
_LANGUAGES = _QWEN_LANGUAGES + _MMS_LANGUAGES
_SPEAKERS = [("Ryan", "Ryan · English (m)"), ("Aiden", "Aiden · English (m)"),
             ("Vivian", "Vivian · Chinese (f)"), ("Serena", "Serena · Chinese (f)"),
             ("Uncle_Fu", "Uncle Fu · Chinese (m)"), ("Dylan", "Dylan · Beijing (m)"),
             ("Eric", "Eric · Sichuan (m)"), ("Ono_Anna", "Ono Anna · Japanese (f)"),
             ("Sohee", "Sohee · Korean (f)")]


class TextToSpeechFeature(Feature):
    id = "text2speech"
    name = "Text → Speech"
    description = "Qwen3-TTS — design a voice from a description, use a preset, or clone from a sample."
    inputs = ["audio"]                 # optional reference clip (cloning); does NOT gate Generate
    engine = "local"
    needs_comfy = False
    icon = "speech"
    est_runtime = "~3–20 s"
    vram = "~4–6 GB"
    output_kinds = ["Speech WAV"]
    guide = [
        {"h": "Engine",
         "b": "Qwen3-TTS (Alibaba, open weights) for 10 languages with full design + cloning: "
              "English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian."},
        {"h": "Hindi & Urdu",
         "b": "Qwen3-TTS has no Hindi/Urdu, so those route to MMS-TTS (also on this box) — one clean "
              "fixed voice each. Type Hindi in Devanagari, Urdu in Nastaʿlīq. Design / cloning / preset "
              "don't apply to these two (MMS has a single voice)."},
        {"h": "Voice design",
         "b": "Describe the voice in plain words (gender, age, tone, emotion, pace, accent) and "
              "Qwen invents it. e.g. 'a warm, calm middle-aged man, speaking slowly and gently'."},
        {"h": "Voice cloning",
         "b": "Switch Mode to Voice cloning, upload a clean ~5–15 s clip of one speaker, and "
              "(recommended) paste its transcript in Reference transcript for a closer match."},
        {"h": "First run",
         "b": "Each mode downloads its Qwen3-TTS checkpoint once (~1.7B). One is kept in VRAM at "
              "a time; switching mode reloads. Needs 'pip install -U qwen-tts' on the box."},
    ]
    params = [
        ParamSpec("text", "text", "", "Text",
                  placeholder="Type what you want spoken…"),
        ParamSpec("mode", "select", "design", "Mode", control="seg",
                  help="Design = invent a voice from a description · Clone = copy a sampled voice · "
                       "Preset = a built-in Qwen speaker.",
                  choices=[{"value": "design", "label": "Voice design"},
                           {"value": "clone", "label": "Voice cloning"},
                           {"value": "preset", "label": "Preset voice"}]),
        ParamSpec("language", "select", "English", "Language",
                  help="Language of the text you typed.",
                  choices=[{"value": l, "label": l} for l in _LANGUAGES]),
        ParamSpec("instruct", "text", "", "Voice description",
                  depends_on={"param": "mode", "value": "design"},
                  placeholder="A warm, calm middle-aged man, clear and expressive, speaking gently.",
                  help="Describe the voice: gender, age, tone, emotion, pace, accent. Qwen turns "
                       "this into a voice — change it and the voice changes."),
        ParamSpec("speaker", "select", "Ryan", "Preset voice",
                  depends_on={"param": "mode", "value": "preset"},
                  help="One of Qwen3-TTS's 9 built-in speakers.",
                  choices=[{"value": v, "label": lbl} for v, lbl in _SPEAKERS]),
        ParamSpec("ref_text", "text", "", "Reference transcript",
                  depends_on={"param": "mode", "value": "clone"},
                  placeholder="Exact words spoken in the uploaded clip (optional, improves accuracy).",
                  help="Transcript of the reference audio. Optional but recommended for a closer clone."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper",
                  group="advanced", help="0 = random each run."),
    ]

    def run(self, inputs, params, out_dir):
        import models_tts
        text = (params.get("text") or "").strip()
        if not text:
            raise ValueError("Enter some text to speak.")
        mode = params.get("mode", "design")
        language = params.get("language", "English")
        seed = int(params.get("seed") or 0)

        if language in _MMS_LANGUAGES:
            # Qwen3-TTS has no Hindi/Urdu → MMS single voice (design/clone/preset don't apply)
            audio, sr = models_tts.synthesize_mms(text, "hi" if language == "Hindi" else "ur")
        elif mode == "clone":
            ref = inputs.get("audio") or inputs.get("image")
            if not ref:
                raise ValueError("Voice cloning needs a reference clip — upload a clean ~5–15 s "
                                 "WAV/MP3, or switch Mode to Voice design.")
            audio, sr = models_tts.synthesize_clone(text, ref, params.get("ref_text", ""),
                                                    language=language, seed=seed)
        elif mode == "preset":
            audio, sr = models_tts.synthesize_preset(text, params.get("speaker", "Ryan"),
                                                     language=language, seed=seed)
        else:
            instruct = (params.get("instruct") or "").strip() \
                or "A clear, natural, expressive voice with a neutral tone."
            audio, sr = models_tts.synthesize_design(text, instruct, language=language, seed=seed)

        out = Path(out_dir) / "speech.wav"
        models_tts.write_wav(out, audio, sr)
        return {"audio": str(out)}
