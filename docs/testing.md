# Supported tests

The automated suite checks the currently supported no-key manual browser workflow. Install `requirements-dev.txt`, then run:

```bash
python -m compileall -q app.py config.py routes/upload.py services/claude_pipeline.py tests/backend
python -m pytest -q --cov=app --cov=routes.upload --cov=services.claude_pipeline --cov-report=term-missing
node --test tests/browser/*.test.js
```

For the JavaScript syntax check used by CI, run `node --check` on each `.js` file in `static/`, `animations/`, and `tests/browser/`. CI has separate backend and browser jobs on every push and pull request. The backend job installs Python dependencies and runs syntax, contract, physics, upload, and Python coverage checks. The browser job runs Node syntax and frontend/renderer contract tests. No API key is needed. Coverage measures `app.py`, `routes/upload.py`, and the active `services/claude_pipeline.py`, including its optional Claude branch in the denominator; it has no minimum threshold.

The backend suite includes the physics assumptions, upload contract, and HTTP-to-JavaScript adapter checks. `scripts/self_check.py` remains an optional diagnostic against a running server; it can also exercise the optional live Claude path when configured. `tests/browser/test_animation_merge.js` remains a renderer fixture invoked by `physics_parameters.test.js`; `tests/browser/QUICK_TEST.js` is a manual browser console helper.

The former OCR and separate text-analysis experiments and their diagnostic tools were removed in Phase 5 because they were outside the supported app path. See [architecture](architecture.md) and the [removal record](archive/pipeline/PHASE5_LEGACY_REMOVAL.md). CI covers the supported manual workflow and mocked image dispatch; a live Claude call still requires a key and is not part of CI.
