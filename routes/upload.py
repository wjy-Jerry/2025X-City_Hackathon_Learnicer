import logging
from flask import Blueprint, request, jsonify, current_app

from services.claude_pipeline import process_image, get_pipeline_status

upload_bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    """检查文件类型是否允许"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@upload_bp.post("/upload")
def upload():
    """
    接收题目图片 -> Claude 多模态 Pipeline (OCR + 解析 + 动画指令) -> 返回统一 JSON

    输入类型决定处理路径：图片使用 Claude；manual_text 使用本地规则解析。

    请求参数：
    - file: 图片文件（claude 模式必需）
    - manual_text: 手动输入的题目文本（manual 模式必需）

    返回格式：
    {
        "problem_type": str,
        "problem_text": str,
        "solution_steps": list[str],
        "animation_instructions": dict | null,
        "assumptions": list[dict],
        "warnings": list[str],
        "parameters": dict (可选)
    }
    """
    # 1. 获取 manual_text（如果有）
    manual_text = request.form.get("manual_text", "").strip() or None

    # 2. 处理图片上传（如果有）
    image_bytes = None
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename != "":
            # 检查文件类型
            if not allowed_file(f.filename):
                return jsonify({
                    "error": "unsupported_file_type",
                    "message": f"不支持的文件类型，仅支持: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}"
                }), 400

            # 读取图片字节（不保存到磁盘，直接传给 Claude）
            try:
                image_bytes = f.read()
                logger.info(f"收到图片: {f.filename}（{len(image_bytes)} 字节）")
            except Exception as e:
                logger.error(f"读取图片失败: {e}")
                return jsonify({
                    "error": "file_read_failed",
                    "message": "读取图片失败",
                    "details": str(e)
                }), 500

    # 3. 输入由 process_image 根据实际内容分派；manual_text 优先于图片。
    if not manual_text and not image_bytes:
        # 什么都没有，返回错误
        return jsonify({
            "error": "missing_input",
            "message": "请提供图片文件或 manual_text 参数",
            "examples": {
                "claude_mode": "curl -X POST .../upload -F 'file=@image.jpg'",
                "manual_mode": "curl -X POST .../upload -F 'manual_text=题目文本'"
            }
        }), 400

    # 4. 调用 Claude Pipeline 或 Manual Pipeline
    try:
        result = process_image(
            image_source=image_bytes,
            manual_text=manual_text
        )

        logger.info(f"✅ Pipeline 处理成功: {result.get('problem_type')}")

    except ValueError as e:
        # 参数错误（400）
        logger.error(f"参数错误: {e}")
        return jsonify({
            "error": "invalid_request",
            "message": "请求参数错误",
            "details": str(e)
        }), 400

    except RuntimeError as e:
        # Pipeline 执行失败（500）
        logger.error(f"Pipeline 失败: {e}")
        error_msg = str(e)

        # 不泄露 API Key（如果错误消息中包含）
        if "api" in error_msg.lower() and "key" in error_msg.lower():
            error_msg = "API 调用失败，请检查环境变量配置"

        return jsonify({
            "error": "pipeline_failed",
            "message": "处理失败",
            "details": error_msg,
            "suggestion": "请检查日志或切换到 manual 模式"
        }), 500

    except Exception as e:
        # 未知错误（500）
        logger.error(f"未知错误: {e}", exc_info=True)
        return jsonify({
            "error": "unknown_error",
            "message": "未知错误",
            "details": str(e)
        }), 500

    # 5. 构建响应（统一格式）
    try:
        response = {
            "problem_type": result.get("problem_type", "unknown"),
            "problem_text": result.get("problem_text", ""),
            "solution_steps": result.get("solution_steps", []),
            "animation_instructions": result.get("animation_instructions"),
            "assumptions": result.get("assumptions", []),
            "warnings": result.get("warnings", []),
        }

        # 可选：附加原始参数（方便前端调试）
        if "parameters" in result:
            response["parameters"] = result["parameters"]

        logger.info("✅ 响应构建成功")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"构建响应失败: {e}")
        return jsonify({
            "error": "response_build_failed",
            "message": "构建响应失败",
            "details": str(e)
        }), 500


@upload_bp.get("/pipeline/status")
def pipeline_status():
    """
    Pipeline 状态检查接口（用于调试和健康检查）

    返回：
    {
        "mode": "claude/manual",
        "claude_configured": bool,
        "error": Optional[str]
    }
    """
    try:
        status = get_pipeline_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"获取 Pipeline 状态失败: {e}")
        return jsonify({
            "error": "status_check_failed",
            "message": "获取 Pipeline 状态失败",
            "details": str(e)
        }), 500
