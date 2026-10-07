# Upload API contract (v0.3)

The main page and `POST /upload` use this contract. `problem_text` is canonical; no `ocr_text` alias is returned. Both input paths produce the same response shape. Version 0.3 adds explicit assumptions and warnings, and makes animation instructions nullable.

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
| `animation_instructions` | object or null | Validated animation, or null when conditions are missing, invalid, conflicting or unsupported |
| `parameters` | object | Effective physical inputs; unknown optional values remain null. Values filled by assumptions are recorded below |
| `assumptions` | object[] | Each entry has `parameter` (string), `value` (number), `reason` (string). Includes inferred direction and model assumptions |
| `warnings` | string[] | Readable explanation of missing, invalid, conflicting or unsupported conditions; currently any warning blocks animation |

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
    "mass": null,
    "duration": 1.2777531299998799,
    "scale": 30
  },
  "parameters": {
    "initial_speed": 10,
    "angle": 0,
    "initial_height": 8,
    "gravity": 9.8,
    "mass": null,
    "duration": null,
    "friction": null
  },
  "assumptions": [
    {"parameter": "air_resistance", "value": 0, "reason": "动画使用理想抛体/自由落体模型，忽略空气阻力，落到参考地面 y=0 时结束。"},
    {"parameter": "angle", "value": 0, "reason": "由水平抛出推得发射角为 0°。"}
  ],
  "warnings": []
}
```

The browser displays text, steps, assumptions and warnings before attempting animation. Null or absent instructions leave the canvas blank and playback controls hidden; arrays never trigger a sample animation. It shows an error for malformed instructions.

## Physics input policy

Units are SI: speed in m/s, height in m, gravity in m/s², mass in kg, duration in s, and launch angle in degrees. The manual parser recognizes a limited set of Chinese phrases and named decimal values, not arbitrary mathematical expressions or unit conversions. Common unsupported units (such as km/h, cm, grams and radians) trigger a warning; fractional/scientific values are not partially parsed as a different number. If a required value cannot be parsed, the API asks the user to supply it. Use explicit labels such as `初速度=20m/s，角度=45°，初始高度=0米，g=9.8`.

| Motion | Required input | Allowed explicit assumptions/inferences |
| --- | --- | --- |
| Projectile | Initial speed and angle | Gravity 9.8 if absent; height 0 if absent; angle 0 only when speed is explicitly zero |
| Horizontal launch | Initial speed and height | Angle 0 inferred from horizontal launch; gravity 9.8 if absent |
| Vertical throw | Initial speed | Angle 90 inferred; gravity 9.8 and ground-level height 0 if absent |
| Free fall | Height | Speed 0 inferred from release at rest; vertical angle convention 90; gravity 9.8 if absent |
| Uniform straight motion | Initial speed | Direction 0, reference height 0 and a 5-second demonstration window if absent |

- All filled values have reasons in `assumptions`; explicit zero speed, angle, height and duration are preserved. A supplied value in unsupported numeric notation triggers a warning and is never treated as an absent parameter eligible for a fallback assumption.
- Gravity and supplied mass must be positive. Speed, height, duration and friction must be nonnegative. Launch angles outside 0–90° are rejected by the current renderer.
- Mass is optional for kinematics. Unknown mass remains null; no mass label or fabricated weight is displayed. Uniform motion does not imply zero gravity: unknown weight is unavailable, not zero.
- Projectile/free-fall duration is **derived time to the reference ground**, not a fixed or minimum duration. An explicitly zero flight time stays zero. Uniform duration is supplied time or the visibly labeled 5-second demonstration window.
- Ballistic animations use the ideal model without air resistance and stop at reference ground `y=0`. Unless neglect of air resistance is explicit in the problem, this model assumption appears in `assumptions`. Requests to consider resistance, friction or rebound are blocked instead of silently ignored.
- Coordinate origin `initial_x=0`, circle layout, pixel scale, colors, object drawing radius, grid and frame rate are display conventions. They do not invent a launch speed, height, force, mass or flight time.
- Unknown motion and inclined-plane problems receive warnings and null instructions. The existing acceleration/circular renderer classes remain available to explicit fixtures, but the active parser does not generate those motions. Their force, friction, mass, radius, angular speed, phase and duration must be supplied; they have no physics fallback values. Rebound fixtures must explicitly provide restitution (`bounceLoss`).

### Insufficient input (HTTP 200)

```json
{
  "problem_type": "horizontal_projectile",
  "problem_text": "水平抛出，初速度=10m/s，角度=0°，g=9.8，忽略空气阻力。",
  "solution_steps": ["解析题干：...", "条件不足或存在冲突，未生成动画；请查看警告并补充题目。"],
  "parameters": {"initial_speed": 10, "angle": 0, "initial_height": null, "gravity": 9.8, "mass": null, "duration": null, "friction": null},
  "animation_instructions": null,
  "assumptions": [],
  "warnings": ["缺少必要参数：初始高度 (initial_height)；请补充后再播放动画。"]
}
```

Incomplete physics conditions are a successfully parsed request, not a transport error. The browser renders the warning and never substitutes a demonstration trajectory.

## Claude extraction validation

The model extracts text, motion type, parameters and literal `parameter_evidence`. It is instructed to leave absent values null. The backend reparses recognized text and requires matching numeric evidence for additional supplied values. Unverifiable or conflicting values cause a warning and block animation. Model-supplied animation instructions are ignored; both input paths build instructions through the same validation/assumption policy. This does not independently guarantee image OCR accuracy.

See [physics default audit](physics_assumptions.md) for the validation policy and removed defaults.

## Error response (HTTP 4xx or 5xx)

Errors return JSON with `error` (machine-readable category) and `message` (user-facing text). `suggestion` and `details` may also be present. The main page shows `message` and `suggestion`; it does not depend on `details`.

```json
{
  "error": "missing_input",
  "message": "请提供图片文件或 manual_text 参数"
}
```

`GET /health` returns `{ "status": "ok" }`. `GET /pipeline/status` reports server configuration; sending `manual_text` still selects rule-based parsing regardless of the configured pipeline mode.
