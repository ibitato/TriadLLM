# FAQ

## The app starts, but it cannot answer anything

Most often, one of these is missing:

- `profiles.yaml` is not in the user config directory
- the chosen profile ids do not exist
- the required API key environment variables are not exported

Check:

- `/status`
- `/models`
- `/config`

## Where are the logs?

Typical Linux path:

```bash
~/.local/state/TriadLLM/log/triadllm.log
```

Useful command:

```bash
tail -f ~/.local/state/TriadLLM/log/triadllm.log
```

## Why is the app waiting on a modal?

You are probably in `ask` permission mode and a model requested a tool.

Approve or deny it with:

- `Enter` or `a` to approve
- `Esc`, `d`, or `q` to deny

To disable prompts for a session:

```text
/permissions yolo
```

## How do I start a completely fresh conversation?

Use:

```text
/new
```

This clears the runtime conversation state and starts a new session file.

## What is the difference between `/new` and `/clear`?

- `/new`: resets the conversation state and starts a new session
- `/clear`: clears only the rendered transcript

`/clear` does not reset the runtime history.

## How do I switch the UI language?

Use:

```text
/lang en
/lang es
```

Fresh installs default to English.

## How do I hide reasoning or tool output?

Use:

```text
/reasoning off
/toolresults off
```

Use `on` to show them again.

## Can I use different providers in different roles?

Yes.

Any supported provider family can be assigned to any of:

- `orchestrator`
- `processor`
- `validator`

That includes:

- OpenAI
- Mistral
- OpenAI-compatible local endpoints

## Does the app use native provider tool calling?

No.

TriadLLM uses its own provider-agnostic structured protocol. Models request tools through JSON, and the runtime executes them through the central broker.

## Why did the model ask for a tool instead of answering directly?

Because the prompt and runtime allow evidence gathering when it materially improves the answer. This is expected, especially for:

- file inspection
- local validation
- command output
- environment checks

## Does TriadLLM support local models?

Yes, as long as they expose an OpenAI-compatible API.

Example:

- `http://127.0.0.1:8080/v1`

## Does TriadLLM load `.env` automatically?

No.

Export the required environment variables before launch, or use your shell startup files or process manager.
