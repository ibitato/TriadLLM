# Changelog

## 0.1.0

Initial public TriadLLM release.

Highlights:

- terminal-first TUI built with `Textual`
- three-stage LLM workflow:
  - `processor`
  - `validator`
  - `orchestrator`
- provider support for:
  - OpenAI
  - Mistral
  - OpenAI-compatible local endpoints
- local tool broker with `ask` and `yolo` permission modes
- slash commands for runtime control
- toggleable reasoning visibility
- toggleable tool request/result visibility
- English-first repository and default runtime language
- migration support from the legacy `MultiBrainLLM` local config layout
- structured rotating logs
- JSONL session persistence
