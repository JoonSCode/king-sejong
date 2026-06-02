# Security Policy

King Sejong includes Codex skills, hook metadata, installer scripts, validation helpers, and runtime-context contracts. Security reports are welcome, especially for issues that could weaken protected-path checks, leak runtime state, or cause unsafe agent execution.

## Supported Versions

King Sejong is currently early-stage. Security fixes are made on `main` and should be consumed from the latest public commit or release.

## Reporting A Vulnerability

Report security issues privately to the repository maintainer through GitHub's private vulnerability reporting if it is enabled. If that is not available, open a minimal public issue that says a private security report is needed, without including exploit details.

Do not include secrets, private Codex session logs, API keys, local filesystem contents, or private repository data in a public issue.

## Relevant Surfaces

Security-sensitive areas include:

- `scripts/install-sejong.sh`
- `docs/sejong/scripts/king_sejong_hooks.py`
- `docs/sejong/scripts/sejong_context.py`
- `docs/sejong/scripts/sillok_trace.py`
- `docs/sejong/scripts/team_executor.py`
- `plugins/king-sejong/hooks/`
- schemas under `docs/sejong/`

## Expected Review

Security fixes should include focused tests or validation evidence. For hook, installer, active-context, or trace changes, run:

```bash
python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py' -v
python3 docs/sejong/scripts/validate_json_contracts.py
bash scripts/install-sejong.sh --verify .
```

Use the documented Sejong/Uigwe/Seungjeongwon flow for material behavior changes so the rationale, affected surfaces, and verification evidence are explicit.
