# Releasing

This repository currently uses a simple release flow.

## Pre-release checks

From the repository root:

```bash
uv sync --dev
uv run pytest -q
uv run python -m compileall src tests docs
uv build
```

## Versioning

The package version lives in:

- `pyproject.toml`

The public release history lives in:

- `CHANGELOG.md`

Update both before creating a new release.

## GitHub Actions

The repository CI workflow runs:

- `uv sync --dev`
- `uv run pytest -q`
- `uv run python -m compileall src tests docs`
- `uv build`

Workflow file:

- `.github/workflows/ci.yml`

## Creating a Release

Typical steps:

1. update `pyproject.toml` version if needed
2. update `CHANGELOG.md`
3. commit and push `main`
4. create an annotated git tag
5. push the tag
6. create the GitHub release

Example:

```bash
git tag -a v0.1.1 -m "TriadLLM v0.1.1"
git push origin v0.1.1
gh release create v0.1.1 --title "TriadLLM v0.1.1" --notes-file RELEASE_NOTES.md
```

## Release Notes Content

Keep release notes concise:

- what changed for users
- major architectural or compatibility notes
- any migration notes
- current limitations if they matter
