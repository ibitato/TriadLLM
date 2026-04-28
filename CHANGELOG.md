# Changelog

## 0.2.0

Minor release with usability improvements, a new startup script, and security dependency updates.

Highlights:

- added `run_triadllm.sh` startup script that checks prerequisites, sets up the environment, and launches the app
- implemented `/config edit` command with a scrollable TUI settings editor
- enhanced `/help` with detailed markdown-formatted command descriptions
- enhanced `/config` with human-friendly formatted output
- resolved three Dependabot security alerts:
  - `pytest` ≥9.0.3 — vulnerable tmpdir handling (medium)
  - `Pygments` ≥2.20.0 — ReDoS in GUID matching (low)
  - `requests` ≥2.33.0 — insecure temp file reuse (medium)

## 0.1.1

Incremental release focused on TUI stability, usability, and presentation polish.

Highlights:

- fixed the permission modal flow so approval prompts resolve reliably from worker-driven turns
- centered permission prompts correctly in the terminal UI
- upgraded the composer to a two-line multiline input with:
  - `Enter` to send
  - `Ctrl+J` to insert a newline
  - `Ctrl+E` to open an expanded editor
- added an expanded composer modal with `Ctrl+S` to send and `Esc` to cancel
- introduced FIFO message queueing while a turn is already running
- added explicit active-turn cancellation via the `Cancel` button and `/cancel`
- added a startup ASCII splash screen that dismisses on any key or after 5 seconds
- refreshed the README branding with a stable SVG logo for GitHub rendering
- expanded TUI coverage for:
  - permission modal behavior
  - composer keyboard shortcuts
  - expanded editor send flow
  - queued-turn processing
  - turn cancellation
  - splash screen dismissal

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
