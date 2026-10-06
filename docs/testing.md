# Supported tests

The automated suite checks the currently supported no-key manual browser workflow. Install `requirements-dev.txt`, then run:

```bash
python -m compileall -q app.py config.py routes/upload.py services/claude_pipeline.py tests/backend
python -m pytest -q --cov=app --cov=routes.upload --cov=services.claude_pipeline --cov-report=term-missing
node --test tests/browser/*.test.js
```

For the JavaScript syntax check used by CI, run `node --check` on each `.js` file in `static/`, `animations/`, and `tests/browser/`. CI has separate backend and browser jobs on every push and pull request. The backend job installs Python dependencies and runs syntax, contract, physics, upload, and Python coverage checks. The browser job runs Node syntax and frontend/renderer contract tests. No API key is needed. Coverage measures `app.py`, `routes/upload.py`, and the active `services/claude_pipeline.py`, including its optional Claude branch in the denominator; it has no minimum threshold.

The previous `tests/test_physics_assumptions.py` is now `tests/backend/test_physics_assumptions.py`; pytest runs its existing assertions. The HTTP contract cases from `scripts/test_upload_endpoint.py` and the real JavaScript adapter check from `scripts/test_frontend_integration.py` are now in `tests/backend/test_http_api.py`, so those duplicate scripts were removed. `scripts/self_check.py` remains an optional diagnostic against a running server; it can also exercise the optional live Claude path when configured. `tests/browser/test_animation_merge.js` remains a renderer fixture invoked by `physics_parameters.test.js`; `tests/browser/QUICK_TEST.js` is a manual browser console helper.

`scripts/quick_test.py` and `scripts/test_dynamic_response.py` exercise legacy OCR/LLM diagnostics. `tools/test_ocr.py` belongs to the legacy OCR path and is known to target an obsolete interface; it is excluded from the supported suite and scheduled for later architecture cleanup. Passing CI does not mean every historical utility works.
