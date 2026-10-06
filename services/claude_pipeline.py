"""Claude 多模态一体化 Pipeline
统一处理：OCR（从图片提取题目文本） + 题目解析 + 动画指令生成

环境变量依赖：
- CLAUDE_API_KEY: Claude API 密钥（必需，claude 模式）
- CLAUDE_MODEL: Claude 模型名称（可选，默认 claude-sonnet-4-5-20250929）
- PIPELINE_MODE: claude/manual（可选，默认 claude）
"""

import base64
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

from anthropic import Anthropic

logger = logging.getLogger(__name__)


# ==================== 配置 ====================

def get_pipeline_mode() -> str:
    """获取当前 Pipeline 模式

    Returns:
        'claude' 或 'manual'
    """
    return os.environ.get("PIPELINE_MODE", "claude").lower()


def get_claude_credentials() -> tuple[str, str]:
    """获取 Claude API 配置

    Returns:
        (api_key, model)

    Raises:
        RuntimeError: 环境变量未设置
    """
    api_key = os.environ.get("CLAUDE_API_KEY", "").strip()
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929").strip()

    if not api_key:
        raise RuntimeError(
            "Claude API Key 未配置！\n"
            "请设置环境变量：\n"
            "  export CLAUDE_API_KEY=your_api_key\n"
            "或使用 manual 模式：\n"
            "  export PIPELINE_MODE=manual"
        )

    logger.info(f"✅ Claude API 配置已加载（model: {model}）")
    return api_key, model


# ==================== Claude 多模态调用 ====================

CLAUDE_SYSTEM_PROMPT = """你是一个物理题 OCR + 解析专家。你的任务是：

1. **OCR**：从图片中提取完整的题目文字（包括中英文、数字、数学公式）
2. **题型识别**：判断运动类型（平抛、自由落体、竖直上抛、斜抛、匀速直线、斜面等）
3. **参数提取**：提取关键物理参数（初速度、角度、高度、重力加速度、摩擦系数等）
4. **解题步骤**：生成清晰的解题步骤（至少 3 步）
5. **证据**：每个参数必须附上题干原文；不得补充未给出的物理值或动画参数

**CRITICAL：你必须只返回纯 JSON，不要包含任何 Markdown 代码块标记（如 ```json），不要有任何解释性文字。**
"""

CLAUDE_USER_PROMPT = """识别物理题并返回纯 JSON：
{
  "problem_text": "完整题目文字",
  "problem_type": "projectile/horizontal_projectile/free_fall/vertical_throw/uniform/inclined_plane/unknown",
  "parameters": {
    "initial_speed": null, "angle": null, "initial_height": null,
    "gravity": null, "mass": null, "duration": null, "friction": null
  },
  "parameter_evidence": {"initial_speed": "题目中包含该数值和单位的原文片段"},
  "solution_steps": [],
  "warnings": []
}
只提取题目明确给出的参数，不得补充速度、角度、重力、高度、质量或时长。
未给出的参数必须为 null。每个数值必须有 parameter_evidence 原文证据。
无法确定题型时返回 unknown。不要伪造解题结果；缺少必要条件时说明缺失。
后端将单独验证参数、记录假设并计算动画，勿自行生成动画参数。
"""

def encode_image_to_base64(image_source: Union[str, bytes, Path]) -> tuple[str, str]:
    """将图片编码为 base64

    Args:
        image_source: 图片路径（str/Path）或图片字节（bytes）

    Returns:
        (base64_string, mime_type)

    Raises:
        FileNotFoundError: 图片文件不存在
        ValueError: 不支持的图片格式
    """
    # 读取图片字节
    if isinstance(image_source, bytes):
        image_data = image_source
        # 根据文件头判断格式
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        elif image_data[:2] == b'\xff\xd8':
            mime_type = "image/jpeg"
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            mime_type = "image/gif"
        elif image_data[:4] == b'WEBP':
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"  # 默认
    else:
        # 路径方式
        image_path = Path(image_source)
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        with open(image_path, "rb") as f:
            image_data = f.read()

        # 根据扩展名判断格式
        suffix = image_path.suffix.lower()
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = mime_map.get(suffix, 'image/jpeg')

    # 编码为 base64
    base64_string = base64.standard_b64encode(image_data).decode('utf-8')

    logger.info(f"✅ 图片已编码为 base64（{len(base64_string)} 字符，类型: {mime_type}）")
    return base64_string, mime_type


def clean_json_response(text: str) -> str:
    """清理 Claude 返回的文本，移除 Markdown 代码块标记"""
    text = text.strip()

    # 移除开头的 ```json 或 ```
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    # 移除结尾的 ```
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_and_normalize_response(data: dict) -> dict:
    """Validate extracted values; never trust model-supplied animation defaults."""
    if not isinstance(data, dict) or not isinstance(data.get("problem_text"), str) or not data["problem_text"].strip():
        raise ValueError("缺少 problem_text 字段或为空")
    text = data["problem_text"].strip()
    params = extract_parameters(text)
    warnings = [w for w in data.get("warnings", []) if isinstance(w, str)] if isinstance(data.get("warnings"), list) else []
    evidence = data.get("parameter_evidence", {})
    evidence = evidence if isinstance(evidence, dict) else {}
    supplied = data.get("parameters", {})
    supplied = supplied if isinstance(supplied, dict) else {}
    for key in params:
        value = supplied.get(key)
        if value is None:
            continue
        if params[key] is not None:
            if value != params[key]:
                warnings.append(f"{key} 的模型值与题干数值不一致，使用题干中提取的数值。")
            continue
        quote = evidence.get(key)
        if is_number(value) and isinstance(quote, str) and quote in text and extract_parameters(quote).get(key) == value:
            params[key] = value
        else:
            warnings.append(f"{key} 缺少可核对的题干证据，未采用模型提供的数值。")
    motion_type = data.get("problem_type") or "unknown"
    detected = detect_motion_type(text)
    if detected != "unknown" and motion_type != detected:
        warnings.append("模型题型与题干识别出的运动类型不一致，请确认题目；未生成动画。")
        motion_type = detected
    result = build_physics_result(text, motion_type, params, warnings)
    if result["animation_instructions"] is not None and isinstance(data.get("solution_steps"), list):
        steps = [s for s in data["solution_steps"] if isinstance(s, str)]
        # Model solutions may rely on unstated assumptions; retain them only for fully specified input.
        if steps and not result["assumptions"]:
            result["solution_steps"] = steps
    return result


def estimate_duration(motion_type: str, v0: float, angle: float, g: float, h0: float) -> float:
    """Derive flight time only from validated inputs, including valid zero values."""
    if motion_type == "free_fall":
        return math.sqrt(2 * h0 / g)
    vy0 = v0 * math.sin(math.radians(angle))
    return (vy0 + math.sqrt(vy0 * vy0 + 2 * g * h0)) / g


def estimate_scale(motion_type: str, v0: float, angle: float, g: float, h0: float, duration: float) -> float:
    """Visual scale has no effect on physical values."""
    if motion_type == "uniform":
        extent_x = abs(v0 * math.cos(math.radians(angle)) * duration)
        extent_y = h0 + abs(v0 * math.sin(math.radians(angle)) * duration)
        return min(620 / max(extent_x, 1), 320 / max(extent_y, 1), 30)
    extent_x = abs(v0 * math.cos(math.radians(angle)) * duration)
    extent_y = h0 + max(v0 * math.sin(math.radians(angle)), 0) ** 2 / (2 * g)
    return min(620 / max(extent_x, 1), 320 / max(extent_y, 1), 30)

def call_claude_pipeline(image_source: Union[str, bytes, Path]) -> dict:
    """调用 Claude 多模态 API 完成 OCR + 解析 + 动画指令生成

    Args:
        image_source: 图片路径或图片字节

    Returns:
        {
            "problem_text": str,
            "problem_type": str,
            "parameters": dict,
            "solution_steps": list[str],
            "animation_instructions": dict | None,
            "assumptions": list[dict],
            "warnings": list[str]
        }

    Raises:
        RuntimeError: API 调用失败
        ValueError: 响应格式错误
    """
    # 1. 获取 API 配置
    api_key, model = get_claude_credentials()

    # 2. 编码图片
    logger.info("开始 Claude 多模态 Pipeline...")
    base64_image, mime_type = encode_image_to_base64(image_source)

    # 3. 构建消息
    client = Anthropic(api_key=api_key)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64_image,
                    },
                },
                {
                    "type": "text",
                    "text": CLAUDE_USER_PROMPT
                }
            ],
        }
    ]

    # 4. 调用 Claude API
    try:
        logger.info(f"正在调用 Claude API（model: {model}）...")
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=messages,
            temperature=0  # 使用确定性输出
        )

        # 5. 提取并解析响应
        raw_text = response.content[0].text
        logger.debug(f"Claude 原始返回: {raw_text[:300]}...")

        # 清理并解析 JSON
        cleaned_text = clean_json_response(raw_text)

        try:
            data = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"原始文本: {cleaned_text[:500]}")
            raise ValueError(f"Claude 返回的不是有效 JSON: {e}")

        # 6. 校验并规范化
        normalized = validate_and_normalize_response(data)

        logger.info(f"✅ Claude Pipeline 成功完成（problem_type: {normalized['problem_type']}）")
        return normalized

    except Exception as e:
        logger.error(f"❌ Claude API 调用失败: {e}")
        raise RuntimeError(f"Claude Pipeline 失败: {e}")


# ==================== Manual 模式（降级方案） ====================

def manual_pipeline(manual_text: str) -> dict:
    """Rule-based parsing; unavailable parameters stay unknown."""
    if not manual_text or not manual_text.strip():
        raise ValueError("manual_text 不能为空")
    text = manual_text.strip()
    return build_physics_result(text, detect_motion_type(text), extract_parameters(text))

def detect_motion_type(text: str) -> str:
    """规则引擎：检测运动类型"""
    if any(kw in text for kw in ["圆周", "匀加速", "匀减速"]):
        return "unknown"  # These are not supported by the active parser.
    # 检查匀速直线运动
    if "匀速" in text and "圆周" not in text:
        return "uniform"

    # 检查自由落体
    if any(kw in text for kw in ["自由落体", "自由下落"]):
        return "free_fall"

    # 检查平抛运动
    if any(kw in text for kw in ["平抛", "水平抛", "水平抛射"]):
        return "horizontal_projectile"

    # 检查竖直上抛
    if "竖直上抛" in text or "竖直抛" in text:
        return "vertical_throw"

    # 检查斜面
    if any(kw in text for kw in ["斜面", "斜坡", "inclined plane"]):
        return "inclined_plane"

    # 检查角度：如果有角度且不是 0 或 90，则为一般抛体
    angle_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[°度]", text)
    if angle_match:
        angle = float(angle_match.group(1))
        if 0 < angle < 90:
            return "projectile"
        elif angle == 90:
            return "vertical_throw"
        elif angle == 0:
            return "horizontal_projectile"

    # 检查斜抛
    if any(kw in text for kw in ["斜抛", "斜向", "角度"]):
        return "projectile"

    # 最后检查一般的"抛"
    if "抛" in text or "弹道" in text or "抛体" in text:
        return "projectile"

    # 无法识别时不伪造题型
    return "unknown"


def extract_parameters(text: str) -> dict:
    """Extract explicit values only; zero is never treated as missing."""
    number = r"(?<![\deE.+/-])([-+]?\d+(?:\.\d+)?)(?![\deE.]|[,/]\d)"
    def find(patterns):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None
    return {
        "initial_speed": find([
            r"(?:初速度|初始速度)\s*(?:为|是|[:：=])?\s*" + number,
            r"\bv0\s*[:：=]\s*" + number,
            r"以\s*" + number + r"\s*(?:m/s|米/秒)(?!\s*的(?:落地|末|最终)速度)",
            number + r"\s*(?:m/s|米/秒)\s*的\s*初速度",
        ]),
        "angle": find([r"(?:角度|angle)\s*[:：=]?\s*" + number, number + r"\s*[°度]"]),
        "initial_height": find([
            r"(?:初始高度|高度|h0)\s*(?:为|是|[:：=])?\s*" + number,
            r"从\s*" + number + r"\s*(?:米|m)(?!/|／)",
            r"高\s*" + number + r"\s*(?:米|m)(?!/|／)",
            number + r"\s*(?:米|m)高",
        ]),
        "gravity": find([r"\bg\s*[:：=]?\s*" + number, r"重力加速度\s*(?:为|是|[:：=])?\s*" + number]),
        "mass": find([r"质量\s*(?:为|是|[:：=])?\s*" + number, r"\bm\s*=\s*" + number]),
        "duration": find([r"(?:持续时间|运动时间|duration)\s*(?:为|是|[:：=])?\s*" + number, r"运动\s*" + number + r"\s*(?:秒|s\b)"]),
        "friction": find([r"摩擦系数\s*[:：=]?\s*" + number, r"μ\s*[:：=]?\s*" + number]),
    }

def generate_solution_steps(motion_type: str, params: dict, text: str) -> list:
    names = {"horizontal_projectile": "平抛运动", "free_fall": "自由落体", "vertical_throw": "竖直上抛", "uniform": "匀速直线", "projectile": "抛体运动", "inclined_plane": "斜面运动"}
    known = ", ".join(f"{key}={value}" for key, value in params.items() if value is not None)
    return [f"解析题干：{text}", f"识别运动类型：{names.get(motion_type, '未确定')}", f"明确给出的参数：{known or '无'}"]


def build_physics_result(text: str, motion_type: str, extracted: dict, warnings=None) -> dict:
    params = dict(extracted)
    warnings = list(warnings or [])
    assumptions = []
    if not isinstance(motion_type, str):
        motion_type = "unknown"
        warnings.append("运动类型必须是字符串；未生成动画。")
    steps = generate_solution_steps(motion_type, params, text)
    supported = {"horizontal_projectile", "vertical_throw", "projectile", "free_fall", "uniform"}
    # A supplied value in unsupported notation is not an absent value. In
    # particular, never read the denominator/exponent as a separate number.
    unsupported_number = r"(?<![\deE.+/-])[-+]?(?:\d+(?:\.\d+)?\s*(?:/\s*\d+(?:\.\d+)?|[eE][-+]?\d+)|\.\d+)"
    labels = {
        "initial_speed": r"(?:初速度|初始速度|\bv0\b)",
        "angle": r"(?:角度|angle)",
        "initial_height": r"(?:初始高度|高度|\bh0\b)",
        "gravity": r"(?:重力加速度|\bg\b)",
        "mass": r"(?:质量|\bm\b)",
        "duration": r"(?:持续时间|运动时间|duration)",
        "friction": r"(?:摩擦系数|μ)",
    }
    invalid_explicit = set()
    for key, label in labels.items():
        if re.search(label + r"\s*(?:为|是|[:：=])?\s*" + unsupported_number, text, re.IGNORECASE):
            invalid_explicit.add(key)
    for key, prefix, suffix in [
        ("initial_speed", r"以\s*", r"\s*(?:m/s|米/秒)"),
        ("angle", "", r"\s*[°度]"),
        ("initial_height", r"(?:从|高)\s*", r"\s*(?:米|m)(?!/|／)"),
        ("duration", r"运动\s*", r"\s*(?:秒|s\b)"),
    ]:
        if re.search(prefix + unsupported_number + suffix, text, re.IGNORECASE):
            invalid_explicit.add(key)
    for key in sorted(invalid_explicit):
        warnings.append(f"无法解析明确给出的 {key}；请使用十进制数值（例如 0.5），不会以默认值替换。")
    def assume(key, value, reason):
        if params.get(key) is None and key not in invalid_explicit:
            params[key] = value
            assumptions.append({"parameter": key, "value": value, "reason": reason})

    if motion_type not in supported:
        warnings.append("未能确定可播放的运动类型，或该运动尚无对应动画；不会替换为抛体示例。")
    else:
        if re.search(r"\d\s*(?:km/h|cm(?:/s)?|mm(?:/s)?|rad(?:/s)?|min\b|分钟|小时|厘米|毫米|千米|公里|弧度)", text, re.IGNORECASE) or re.search(
                r"质量\s*(?:为|是|[:：=])?\s*[-+]?\d+(?:\.\d+)?\s*(?:g\b|克)", text, re.IGNORECASE):
            warnings.append("当前解析器只支持 SI 单位和角度制；请把速度换成 m/s、高度换成 m、质量换成 kg、时间换成秒、角度换成度后重试。")
        if motion_type != "uniform":
            assume("gravity", 9.8, "题目未给出重力加速度，假设地球标准重力 g=9.8 m/s²。")
            if not re.search(r"(?:忽略|不计|无)空气阻力", text):
                assumptions.append({"parameter": "air_resistance", "value": 0,
                                    "reason": "动画使用理想抛体/自由落体模型，忽略空气阻力，落到参考地面 y=0 时结束。"})
            if params.get("friction") is not None or re.search(r"(?:考虑|存在|有)空气阻力|反弹", text):
                warnings.append("当前动画不处理阻力、摩擦或反弹；不会忽略这些条件后生成轨迹。")
        if motion_type == "horizontal_projectile":
            assume("angle", 0, "由水平抛出推得发射角为 0°。")
        elif motion_type == "vertical_throw":
            assume("angle", 90, "由竖直上抛推得发射角为 90°。")
        elif motion_type == "free_fall":
            assume("initial_speed", 0, "自由落体按从静止释放的定义处理，初速度为 0 m/s。")
            assume("angle", 90, "自由落体为竖直运动；初速度为零时角度不影响轨迹。")
        elif motion_type == "uniform":
            assume("angle", 0, "题目未给出方向，演示假设沿水平正方向匀速运动。")
            assume("duration", 5, "题目未给出运动时间，使用 5 秒演示窗口，不代表实际运动总时长。")
        elif params.get("initial_speed") == 0:
            assume("angle", 0, "初速度为零，发射方向不影响轨迹，采用 0° 角度约定。")
        if motion_type in {"projectile", "vertical_throw", "uniform"}:
            assume("initial_height", 0, "题目未给出初始高度，假设从参考地面 y=0 开始。")

        required = ["initial_speed", "angle", "initial_height"]
        if motion_type != "uniform":
            required.append("gravity")
        else:
            required.append("duration")
        labels = {"initial_speed": "初速度", "angle": "发射角度", "initial_height": "初始高度", "gravity": "重力加速度", "duration": "运动时间"}
        for key in required:
            if params.get(key) is None:
                warnings.append(f"缺少必要参数：{labels[key]} ({key})；请补充后再播放动画。")
            elif not is_number(params[key]):
                warnings.append(f"{labels[key]} ({key}) 必须是有限数值。")
        for key in ["initial_speed", "initial_height", "duration", "mass", "gravity", "angle", "friction"]:
            value = params.get(key)
            if value is None:
                continue
            if not is_number(value):
                warnings.append(f"{key} 必须是有限数值。")
                continue
            if value < 0 or (key in {"gravity", "mass"} and value == 0) or (key == "angle" and value > 90):
                warnings.append(f"{key}={value} 超出当前动画支持的范围，不会用默认值替换。")
        if motion_type == "horizontal_projectile" and params.get("angle") != 0:
            warnings.append("水平抛出与给出的非零角度冲突，请确认题干。")
        if motion_type == "vertical_throw" and params.get("angle") != 90:
            warnings.append("竖直上抛与给出的角度冲突，请确认题干。")
        if motion_type == "free_fall" and params.get("initial_speed") != 0:
            warnings.append("自由落体与给出的非零初速度冲突，请确认题干。")

    # Warnings mean the problem is insufficient or inconsistent: no plausible-looking fallback.
    animation = None
    if not warnings:
        animation = generate_animation_instructions(motion_type, params)
        steps.extend(f"明确假设：{a['reason']}" for a in assumptions)
        if motion_type != "uniform":
            steps.append(f"由已确认参数计算落地时间：{animation['duration']:.3f} s。")
            if params.get("duration") is not None:
                steps.append(f"题干运动时间为 {params['duration']} s；此动画展示到参考地面的完整飞行，动画时长使用计算出的落地时间。")
        steps.append("使用上述参数和明确假设生成运动动画。")
    else:
        steps.append("条件不足或存在冲突，未生成动画；请查看警告并补充题目。")
    return {"problem_text": text, "problem_type": motion_type, "parameters": params,
            "solution_steps": steps, "animation_instructions": animation,
            "assumptions": assumptions, "warnings": list(dict.fromkeys(warnings))}


def generate_animation_instructions(motion_type: str, params: dict) -> dict:
    """Called only after validation; no physics fallback values."""
    anim_type = "free_fall" if motion_type == "free_fall" else "uniform" if motion_type == "uniform" else "projectile"
    v0, angle, h0 = params["initial_speed"], params["angle"], params["initial_height"]
    g = params.get("gravity")
    duration = params["duration"] if motion_type == "uniform" else estimate_duration(anim_type, v0, angle, g, h0)
    return {"type": anim_type, "initial_speed": v0, "angle": angle, "gravity": g,
            "initial_x": 0, "initial_y": h0, "mass": params.get("mass"), "duration": duration,
            "scale": estimate_scale(anim_type, v0, angle, g, h0, duration)}


# ==================== 主入口 ====================

def process_image(
    image_source: Optional[Union[str, bytes, Path]] = None,
    manual_text: Optional[str] = None
) -> dict:
    """主入口：处理图片或文本，返回统一的结构化结果

    智能模式选择：
    - 如果提供了 manual_text，优先使用 manual pipeline（无论环境变量如何配置）
    - 如果只提供了 image_source，使用 claude pipeline
    - 这样可以灵活切换，无需修改环境变量

    Args:
        image_source: 图片路径/字节（claude 模式必需）
        manual_text: 手动输入的题目文本（manual 模式必需）

    Returns:
        {
            "problem_text": str,
            "problem_type": str,
            "parameters": dict,
            "solution_steps": list[str],
            "animation_instructions": dict | None,
            "assumptions": list[dict],
            "warnings": list[str]
        }

    Raises:
        ValueError: 参数错误
        RuntimeError: 处理失败
    """
    # 智能模式选择：优先使用 manual_text（如果提供）
    if manual_text and manual_text.strip():
        # 有 manual_text，使用 manual pipeline
        logger.info("✅ 检测到 manual_text，使用 Manual Pipeline")
        return manual_pipeline(manual_text)

    elif image_source:
        # 有图片，使用 claude pipeline
        logger.info("✅ 检测到 image_source，使用 Claude Pipeline")
        return call_claude_pipeline(image_source)

    else:
        # 什么都没有，检查环境变量配置的模式并给出友好提示
        mode = get_pipeline_mode()
        if mode == "manual":
            raise ValueError(
                "manual 模式需要提供 manual_text\n"
                "请在上传请求中添加 manual_text 参数"
            )
        else:
            raise ValueError(
                "claude 模式需要提供 image_source（图片路径或字节）\n"
                "或提供 manual_text 参数以使用 manual 模式"
            )


def get_pipeline_status() -> dict:
    """获取 Pipeline 状态（健康检查）

    Returns:
        {
            "mode": "claude/manual",
            "claude_configured": bool,
            "error": Optional[str]
        }
    """
    mode = get_pipeline_mode()

    status = {
        "mode": mode,
        "claude_configured": False,
        "error": None
    }

    if mode == "claude":
        try:
            get_claude_credentials()
            status["claude_configured"] = True
        except Exception as e:
            status["error"] = str(e)
            status["claude_configured"] = False

    return status
