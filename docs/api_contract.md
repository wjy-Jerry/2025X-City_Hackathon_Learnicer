# Upload API contract (v0.2)

The main page and `POST /upload` use this contract. Version 0.2 replaces the old `ocr_text` field with `problem_text`; no `ocr_text` alias is returned. Both input paths produce the same response shape.

## Request

Send `multipart/form-data` to `POST /upload` with one of these fields:

| Field | Processing | Requirement |
| --- | --- | --- |
| `manual_text` | Rule-based parsing of text; no OCR or Claude call | Nonempty text; no API key needed |
| `file` | Claude image recognition and parsing | PNG or JPG image; `CLAUDE_API_KEY` needed |

Send one field per request. The browser sends only the field for the selected mode. If both valid inputs are supplied, the backend uses `manual_text`.

```bash
curl -X POST http://127.0.0.1:5000/upload \
  -F "manual_text=一个物体从8米高的平台以10m/s的速度水平抛出，g=9.8m/s²，求运动轨迹。"
```

## Successful response (HTTP 200)

| Field | Type | Meaning |
| --- | --- | --- |
| `problem_type` | string | Detected motion category |
| `problem_text` | string | Submitted text in manual mode, or recognized text in image mode |
| `solution_steps` | string[] | Ordered explanation steps |
| `animation_instructions` | object | Instructions passed to the Canvas animation adapter |
| `parameters` | object, optional | Parsed physical parameters |

Example shape (values vary with input):

```json
{
  "problem_type": "horizontal_projectile",
  "problem_text": "一个物体从8米高的平台以10m/s的速度水平抛出，g=9.8m/s²，求运动轨迹。",
  "solution_steps": ["解析题干：...", "识别运动类型：平抛运动"],
  "animation_instructions": {
    "type": "projectile",
    "initial_speed": 10,
    "angle": 0,
    "gravity": 9.8,
    "initial_x": 0,
    "initial_y": 8,
    "duration": 1.28,
    "scale": 30
  },
  "parameters": {
    "initial_speed": 10,
    "angle": null,
    "initial_height": 8,
    "gravity": 9.8,
    "friction": null
  }
}
```

The frontend displays `problem_text` and `solution_steps`, then passes `animation_instructions` through `AnimationEngine.loadInstructions()`.

## Error response (HTTP 4xx or 5xx)

Errors return JSON with `error` (machine-readable category) and `message` (user-facing text). `suggestion` and `details` may also be present. The main page shows `message` and `suggestion`; it does not depend on `details`.

```json
{
  "error": "missing_input",
  "message": "请提供图片文件或 manual_text 参数"
}
```

`GET /health` returns `{ "status": "ok" }`. `GET /pipeline/status` reports server configuration; sending `manual_text` still selects rule-based parsing regardless of the configured pipeline mode.
