# Supported architecture

The browser submits one of two inputs to `POST /upload`:

```text
Browser
├── Manual text ──> local rule-based physics parser ──┐
└── Image ────────> Claude multimodal analysis ─────────┤
                                                       ↓
                                        Unified validated response
                                                       ↓
                                        Solution + Canvas animation
```

`app.py` creates the Flask app and registers `routes/upload.py`. The route checks the upload and delegates both input forms to `services/claude_pipeline.py`. For accepted inputs, nonempty `manual_text` takes precedence and uses `manual_pipeline`; an image uses `call_claude_pipeline`, which sends image bytes to Claude. A missing Claude key produces an error for images, while manual text needs no key. `PIPELINE_MODE` is retained for the existing `/pipeline/status` response; it does not replace the input-based dispatch. `config.py` loads `.env` and holds Flask and Claude settings.

Both paths build the same validated response: `problem_type`, `problem_text`, `solution_steps`, nullable `animation_instructions`, `assumptions`, `warnings`, and optional `parameters`. The Claude path validates extracted values against the recognized text and rebuilds animation instructions locally; model-supplied animation instructions are not trusted. The manual path parses the supplied text locally. The frontend in `templates/index.html`, `static/main.js`, and `static/animation.js` displays the text, steps, assumptions and warnings, and plays an animation only when valid instructions are present. See [API contract](api_contract.md) for field details.

The dependency audit and legacy removal rationale are recorded in the [Phase 5 archive note](archive/pipeline/PHASE5_LEGACY_REMOVAL.md). Passing CI covers the supported key-free manual workflow and a mocked image dispatch; live Claude image analysis requires a configured key and is not exercised in CI.
