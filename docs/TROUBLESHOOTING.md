# Troubleshooting

This guide is for common failure modes when someone clones the repo and tries to run TriadLLM.

## The TUI starts, but there are no profiles

Symptom:

- the app opens
- no model profiles appear in `/models`
- the system message says no provider profiles are configured

Fix:

```bash
mkdir -p ~/.config/TriadLLM
cp src/triadllm/examples/profiles.yaml ~/.config/TriadLLM/profiles.yaml
```

Then export the required API keys and restart the app.

## The app starts, but model calls fail immediately

Check:

- the selected profile ids exist in `profiles.yaml`
- the correct API key environment variables are exported
- the model id is actually available in your tenant

Useful checks:

```text
/status
/models
/config
```

## The app is in the wrong language

Use:

```text
/lang en
```

or:

```text
/lang es
```

Fresh installs default to English.

## Tool permission modal keeps appearing

You are in `ask` mode.

Approve or deny with:

- `Enter` or `a` to approve
- `Esc`, `d`, or `q` to deny

If you want to disable prompts temporarily:

```text
/permissions yolo
```

## A local OpenAI-compatible model is very slow

This is normal on limited hardware.

Recommendations:

- increase provider `timeout`
- reduce model size if possible
- keep `ask` mode off during long tool-heavy experiments if you trust the environment
- test one role at a time first, then assign it into the full pipeline

## The app starts but returns no useful answer

Typical causes:

- provider profiles are missing
- wrong model ids
- wrong API keys
- the local endpoint is not running
- the selected role mix is valid technically but poor for the task

For first success, prefer the simplest setup:

- `default_profile: openai_default`
- export `OPENAI_API_KEY`
- run all three roles through the same profile

## The log file is hard to find

Typical Linux path:

```bash
~/.local/state/TriadLLM/log/triadllm.log
```

Useful command:

```bash
tail -f ~/.local/state/TriadLLM/log/triadllm.log
```

## A migrated install still shows old MultiBrainLLM data

TriadLLM copies legacy config forward on first run.

If you want a completely clean state:

1. remove or rename `~/.config/TriadLLM`
2. remove or rename `~/.local/share/TriadLLM`
3. remove or rename `~/.local/state/TriadLLM`
4. launch the app again

## How to confirm the runtime really sees my config

Inside the app, run:

```text
/config
```

That shows:

- resolved paths
- settings
- loaded profiles
- sample profile location
