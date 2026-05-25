# Ex8 — Voice pipeline

## Your answer

The voice pipeline has two modes with shared trace-event contract:
text mode reads stdin and the
manager persona replies via Llama-3.3-70B-Instruct on Nebius
(manager_persona.py:57); voice mode (run_voice_mode at
voice_loop.py:83) uses sounddevice for mic capture, Speechmatics
realtime websocket for STT, and Rime Arcana for TTS.

The critical design choice is graceful degradation. run_voice_mode
checks SPEECHMATICS_KEY and the
speechmatics-python import before doing
anything else. If either is missing, it logs a warning to stderr
and falls through to run_text_mode. This means CI can pass the
"voice loop implemented" check without Speechmatics credentials —
the same code paths run, just under the simpler transport. (One
gap: PortAudio OSError from sounddevice — voice_loop.py:100 — is
NOT caught by the ImportError handler, so a missing libportaudio2
crashes the run instead of falling back. Easy fix: widen the except
to `(ImportError, OSError)`.)

Both modes emit voice.utterance_in 
and voice.utterance_out trace events
with payload {text, turn, mode}. The mode field tells the grader
which transport was in use. Same trace shape = identical downstream
analysis.

The ManagerPersona class holds a
conversation history list (`history: list[ManagerTurn]`) and calls
the LLM for each turn at `temperature=0.0`
(manager_persona.py:76) — that's what makes it deterministic given
identical history, not an explicit seed parameter. With zero
temperature plus a stable model id, the test_text_mode_appends_trace_events
test in tests/public/test_ex8_scaffold.py stays stable across
runs without seeding work.

## Citations

- starter/voice_pipeline/voice_loop.py — run_text_mode, run_voice_mode, _transcribe_speechmatics
- starter/voice_pipeline/voice_loop.py — _speak_rime, ManagerPersona
- starter/voice_pipeline/manager_persona.py — temperature=0.0 call
