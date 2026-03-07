# Roadmap

## Near Term

- improve provider onboarding with more ready-made profile presets
- add more practical local tools for coding workflows
- make tool argument guidance even more robust across weaker models
- keep improving the permission UX in the TUI
- strengthen end-to-end mixed-provider testing

## Next

- package distribution and release hygiene
- richer troubleshooting and operator docs
- better session inspection and replay tooling
- more explicit provider capability reporting in the UI
- optional export of session transcripts

## Later

- API/server mode in addition to the TUI
- web client consuming the same core runtime
- more formal plugin or extension story for tools
- richer observability around latency, retries, and provider fallbacks
- optional persistence backends beyond local files

## Product Direction

TriadLLM is moving toward a shared core that can power:

- a terminal UI
- an API service
- potentially a web frontend

The stable idea is not “many agents for their own sake,” but:

- primary answer generation
- validation against the original request
- final synthesis for the caller
