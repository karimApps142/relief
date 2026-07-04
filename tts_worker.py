"""tts_worker.py — voice-DESIGN worker, run in the ISOLATED .venv-tts.

Indic Parler-TTS pins transformers==4.46, which conflicts with the app's main venv
(transformers 5.12). So it lives in its own venv and models_tts.py drives it as a
subprocess: JSON request on stdin → writes a WAV to request["out"] → prints a JSON
status line. This file is executed ONLY by .venv-tts's python, never imported by the app.

Set up the venv once (see requirements-gpu.txt), then Design "just works" — the app
auto-detects .venv-tts and routes voice design here; otherwise it falls back to MMS.
"""
import sys
import json


def _synth_design(req):
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    repo = "ai4bharat/indic-parler-tts"
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = ParlerTTSForConditionalGeneration.from_pretrained(repo).to(dev).eval()
    tok = AutoTokenizer.from_pretrained(repo)
    desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)

    if req.get("seed"):
        torch.manual_seed(int(req["seed"]))
    desc = desc_tok(req["description"], return_tensors="pt").to(dev)
    prompt = tok(req["text"], return_tensors="pt").to(dev)
    with torch.inference_mode():
        gen = model.generate(
            input_ids=desc.input_ids, attention_mask=desc.attention_mask,
            prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask)
    audio = gen.to(torch.float32).cpu().numpy().squeeze()
    return audio, int(model.config.sampling_rate)


def main():
    req = json.loads(sys.stdin.read())
    audio, sr = _synth_design(req)                 # design is the only mode for now
    import numpy as np
    import soundfile as sf
    sf.write(req["out"], np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0), int(sr))
    print(json.dumps({"ok": True, "sr": int(sr)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)
