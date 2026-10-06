# Phase 5 legacy OCR/LLM removal

Before Phase 5, the repository contained two parallel experiments outside the supported Flask upload path:

- `services/ocr_service.py` implemented a Mathpix/manual OCR provider selected by `OCR_MODE`. `scripts/quick_test.py` exercised it. `tools/test_ocr.py` referenced an obsolete `get_ocr_provider` function and failed before its checks could run. `switch_ocr_mode.sh` edited `.env` for that provider selector.
- `services/llm_service.py` offered a separate older rule-based/Claude text-analysis path. Only `scripts/test_dynamic_response.py` imported it. Its defaults could imply physics parameters that were not supplied by the problem.
- `utils/json_builder.py` was unreferenced and returned the pre-contract `ocr_text` field.

## Dependency and reference map recorded before removal

| Component | Class | Evidence and disposition |
| --- | --- | --- |
| Flask app, upload route, Claude pipeline | A — active | App registers the route; both supported input paths delegate to the active pipeline. Retain. |
| Flask/Claude config and `.env` loading | A — active | App loads Flask configuration and dotenv; Claude credentials/model remain active. Remove only unused legacy flags. |
| Live-server self-check and `requests` | A — active diagnostic | The optional diagnostic uses health, status, and upload routes. Retain. |
| `Pillow` | C — obsolete dependency | No supported Python source imports its modules; image encoding uses the standard library. Remove. |
| Archived migration/audit documents | B — historical | Records prior experiments; retain only as historical material. |
| Separate OCR service, OCR tests/switch, separate LLM service and its test, old JSON builder | C — obsolete | Imported only by the legacy diagnostics or unreferenced; absent from app routes and supported tests. Remove. |
| `PIPELINE_MODE`, Claude settings, renderer fixtures | D — retain | Needed for status compatibility, image configuration, or browser tests. |

The supported route imported none of the removed services. The active image path sends image bytes directly to Claude multimodal analysis, and the active manual path parses `manual_text` in `services/claude_pipeline.py`. The Phase 4 tests covered the supported behavior without importing the removed services. The legacy implementations and diagnostics were removed rather than repaired. Their source remains available in Git history before Phase 5; older migration reports in this archive remain historical records.

Related obsolete configuration removed from the active app: `OCR_PROVIDER`, `OCR_LANG`, `ENABLE_LLM`, and `HUB_DATASET_ENDPOINT`, including the PaddleOCR environment workaround. The unused `CLAUDE_MAX_TOKENS` setting was also removed; the active Claude request uses its existing `max_tokens=4096` value. `OCR_MODE` and Mathpix credentials existed only inside the removed OCR path. Pillow was removed from runtime requirements after an import audit found no usage. `requests` remains because the optional live-server `scripts/self_check.py` imports it.
