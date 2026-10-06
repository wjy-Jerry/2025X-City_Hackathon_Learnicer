"""HTTP contract for the supported manual browser demo."""

import io
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLETE = "斜抛，初速度=20m/s，角度=45°，初始高度=0米，g=9.8m/s²，忽略空气阻力。"
CASES = [
    ("一小球以 12 m/s 的初速度水平抛出，从 15 米高的平台，g = 9.8 m/s²", "horizontal_projectile"),
    ("一物体从 25 米高处自由落体，重力加速度 g = 9.8 m/s²", "free_fall"),
    (COMPLETE, "projectile"),
    ("匀速直线，初速度=10m/s，角度=0°，高度=0米，运动时间=5秒", "uniform"),
]


def test_health_and_no_key_pipeline_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    status = client.get("/pipeline/status")
    assert status.status_code == 200
    assert status.get_json() == {"mode": "manual", "claude_configured": False, "error": None}


def test_browser_page_exposes_manual_mode_and_scripts(client):
    page = client.get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for element in ('id="manualText"', 'id="manualMode"', 'id="exampleButton"',
                    'id="assumptionsContainer"', 'id="warningsContainer"'):
        assert element in html
    assert client.get("/static/main.js").status_code == 200
    assert client.get("/static/animation.js").status_code == 200


@pytest.mark.parametrize("problem_text, problem_type", CASES)
def test_complete_manual_upload_contract(client, monkeypatch, problem_text, problem_type):
    # The manual path must remain independent of Claude even if mode is set to claude.
    monkeypatch.setenv("PIPELINE_MODE", "claude")
    with patch("services.claude_pipeline.call_claude_pipeline", side_effect=AssertionError("API call")):
        response = client.post("/upload", data={"manual_text": problem_text})
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == {"problem_type", "problem_text", "solution_steps", "animation_instructions",
                         "assumptions", "warnings", "parameters"}
    assert data["problem_text"] == problem_text
    assert "ocr_text" not in data
    assert data["problem_type"] == problem_type
    assert isinstance(data["solution_steps"], list)
    assert all(isinstance(step, str) for step in data["solution_steps"])
    assert isinstance(data["animation_instructions"], dict)
    assert isinstance(data["assumptions"], list)
    assert all({"parameter", "value", "reason"} <= set(item) for item in data["assumptions"])
    assert data["warnings"] == []


def test_missing_gravity_is_visible_in_http_response(client):
    response = client.post("/upload", data={"manual_text": COMPLETE.replace("g=9.8m/s²，", "")})
    assert response.status_code == 200
    data = response.get_json()
    assert data["animation_instructions"]["gravity"] == 9.8
    assert len(data["assumptions"]) == 1
    assert data["assumptions"][0]["parameter"] == "gravity"
    assert data["assumptions"][0]["value"] == 9.8
    assert data["assumptions"][0]["reason"]


@pytest.mark.parametrize("problem_text,missing", [
    ("斜抛，角度=45°，高度=0米，g=9.8", "initial_speed"),
    ("斜抛，初速度=20m/s，高度=0米，g=9.8", "angle"),
    ("水平抛出，初速度=10m/s，g=9.8", "initial_height"),
])
def test_missing_essential_parameter_returns_warning_without_animation(client, problem_text, missing):
    response = client.post("/upload", data={"manual_text": problem_text})
    assert response.status_code == 200
    data = response.get_json()
    assert data["animation_instructions"] is None
    assert any(missing in warning for warning in data["warnings"])
    assert isinstance(data["solution_steps"], list)


@pytest.mark.parametrize("speed,angle,height", [(0, 45, 0), (10, 0, 0), (0, 0, 0)])
def test_zero_parameters_survive_http_response(client, speed, angle, height):
    text = f"抛体，初速度={speed}m/s，角度={angle}°，高度={height}米，g=9.8，忽略空气阻力。"
    response = client.post("/upload", data={"manual_text": text})
    assert response.status_code == 200
    data = response.get_json()
    assert data["warnings"] == []
    animation = data["animation_instructions"]
    assert (animation["initial_speed"], animation["angle"], animation["initial_y"]) == (speed, angle, height)


@pytest.mark.parametrize("data,error", [
    ({}, "missing_input"),
    ({"manual_text": "  "}, "missing_input"),
    ({"file": (io.BytesIO(b"not an image"), "problem.txt")}, "unsupported_file_type"),
    ({"file": (io.BytesIO(b""), "")}, "missing_input"),
])
def test_upload_rejects_missing_or_unsupported_inputs(client, data, error):
    response = client.post("/upload", data=data)
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == error
    assert body["message"]


def test_image_upload_without_key_fails_readably(client, monkeypatch):
    # No network call: the pipeline checks for a configured key first.
    monkeypatch.setenv("PIPELINE_MODE", "claude")
    response = client.post("/upload", data={"file": (io.BytesIO(b"fake png"), "problem.png")})
    assert response.status_code == 500
    data = response.get_json()
    assert data["error"] == "pipeline_failed"
    assert data["message"]
    assert data["suggestion"]


def test_oversized_upload_is_rejected(client):
    response = client.post("/upload", data={"file": (io.BytesIO(b"x" * (10 * 1024 * 1024 + 1)), "problem.png")})
    assert response.status_code == 413


@pytest.mark.parametrize("problem_text,expected", [
    ("一个物体从10米高处以15m/s的初速度水平抛出，g=9.8m/s²", (15, 0, 10)),
    ("一个物体从20米高处以25m/s的初速度水平抛出，g=10m/s²", (25, 0, 20)),
    ("抛体，初速度=30m/s，角度=45°，高度=0米，g=9.8，忽略空气阻力。", (30, 45, 0)),
])
def test_actual_http_payload_reaches_js_adapter(client, problem_text, expected):
    """Preserve the old frontend integration check using the real HTTP payload and adapter."""
    response = client.post("/upload", data={"manual_text": problem_text})
    assert response.status_code == 200
    body = response.get_json()
    assert body["warnings"] == []
    script = """
const fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({window: {}});
for (const file of ['animations/animation_base.js', 'static/animation.js']) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context);
}
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(context.window.AnimationEngine.normalizePayload(payload)));
"""
    result = subprocess.run(["node", "-e", script], input=json.dumps(body["animation_instructions"]),
                            text=True, capture_output=True, check=True, cwd=REPO_ROOT)
    normalized = json.loads(result.stdout)
    assert (normalized["parameters"]["v0"], normalized["parameters"]["angle"],
            normalized["parameters"]["h0"]) == expected
