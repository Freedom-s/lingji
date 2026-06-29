"""
测试 VLM 模型是否真正能"看到"图片内容

测试场景：
1. 从 MinIO 获取一张课件/文档页面的图片
2. 将图片以 base64 形式传入 tool call
3. 要求模型调用 tool 来提取图片中的具体信息（文本、公式、图表描述等）
4. 对比模型输出与实际图片内容，验证视觉能力

用法：
    conda activate ragflowplus
    python test_vlm_image_vision.py
"""
import sys
import os
import json
import base64
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 使用项目已有的 chat_model
from rag.llm.chat_model import OpenAI_APIChat, Base

# MinIO 配置
from minio import Minio

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "rag_flow"
MINIO_SECRET_KEY = "infini_rag_flow"
MINIO_SECURE = False

# 模型配置
API_KEY = 'sk-ddmuwiogctbqpznflymvdrdbasdelejzahfhickpovhlcpzr'
MODEL_NAME = 'Qwen/Qwen3-VL-32B-Instruct'
BASE_URL = 'https://api.siliconflow.cn/v1'


def get_image_base64_from_minio(image_path: str) -> dict | None:
    """从 MinIO 获取图片并返回 base64 data URL 和元信息"""
    logger.info(f"从 MinIO 获取图片: {image_path}")

    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

    if image_path.startswith("minio://"):
        path_without_protocol = image_path[8:]
        parts = path_without_protocol.split('/', 1)
        if len(parts) != 2:
            logger.error(f"无效路径: {image_path}")
            return None
        bucket_name, object_name = parts
    else:
        logger.error(f"不支持的路径格式: {image_path}")
        return None

    logger.info(f"  Bucket: {bucket_name}, Object: {object_name}")

    response = minio_client.get_object(bucket_name, object_name)
    image_data = response.read()
    response.close()
    response.release_conn()

    base64_image = base64.b64encode(image_data).decode('utf-8')

    ext = object_name.lower().split('.')[-1]
    mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'gif': 'image/gif', 'webp': 'image/webp', 'bmp': 'image/bmp'}
    mime_type = mime_map.get(ext, 'image/jpeg')

    data_url = f"data:{mime_type};base64,{base64_image}"

    logger.info(f"✅ 图片获取成功 (size: {len(image_data)} bytes, type: {mime_type})")
    return {
        "data_url": data_url,
        "size_bytes": len(image_data),
        "mime_type": mime_type,
        "object_name": object_name
    }


def test_tool_call_with_image(model: Base, image_info: dict, test_description: str):
    """
    核心测试：将图片放入 tool call 的 history 中，要求模型用 tool 提取图片内容，
    看模型提取的内容是否与图片实际内容一致。
    """
    data_url = image_info["data_url"]
    object_name = image_info["object_name"]

    # 定义工具：要求模型"阅读"图片并提取其中的文字/公式/结构化信息
    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_page_content",
                "description": (
                    "仔细阅读用户提供的图片（课件/文档页面），提取页面中的核心内容。"
                    "包括但不限于：标题、正文文字、公式、图表描述、关键概念等。"
                    "请如实、完整地报告你能看到的内容，不要编造。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_title": {
                            "type": "string",
                            "description": "页面标题或主题（如果能识别的话）"
                        },
                        "main_text": {
                            "type": "string",
                            "description": "页面中的主要正文文字内容，尽可能完整地转录"
                        },
                        "formulas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "页面中出现的数学公式或表达式（文本形式）"
                        },
                        "has_table": {
                            "type": "boolean",
                            "description": "页面中是否包含表格"
                        },
                        "has_diagram": {
                            "type": "boolean",
                            "description": "页面中是否包含图表/插图/流程图"
                        },
                        "diagram_description": {
                            "type": "string",
                            "description": "如果有图表，描述图表展示了什么"
                        },
                        "language": {
                            "type": "string",
                            "description": "页面内容使用的语言 (zh/en/mixed)"
                        },
                        "summary": {
                            "type": "string",
                            "description": "用一句话总结这页的主要内容"
                        }
                    },
                    "required": ["page_title", "main_text", "summary", "language"]
                }
            }
        }
    ]

    # 构建包含图片的消息
    content_parts = [
        {"type": "text", "text": (
            "请仔细查看这张图片（这是一个课件/文档页面），"
            "使用 extract_page_content 工具提取页面中的所有文字内容和结构信息。"
            "请如实报告你能看到的内容，不要遗漏任何文字。"
        )},
        {
            "type": "image_url",
            "image_url": {"url": data_url, "detail": "high"}
        }
    ]

    logger.info(f"\n{'='*80}")
    logger.info(f"测试: {test_description}")
    logger.info(f"图片: {object_name} ({image_info['size_bytes']} bytes)")
    logger.info(f"{'='*80}")

    response = model.chat_with_tools(
        system=(
            "你是一个专业的 OCR 和文档分析助手。"
            "你的任务是用 extract_page_content 工具提取图片中你能看到的所有文字和内容。"
            "关键：必须如实报告，如果看不清就说看不清，不要凭空编造内容。"
        ),
        history=[{"role": "user", "content": content_parts}],
        gen_conf={
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1
        }
    )

    return response


def test_simple_chat_with_image(model: Base, image_info: dict):
    """
    对比测试：直接用 chat 方法（不带 tools），让模型描述图片内容。
    这样可以对比有 tool / 无 tool 情况下模型对图片的理解能力。
    """
    data_url = image_info["data_url"]
    object_name = image_info["object_name"]

    content_parts = [
        {"type": "text", "text": (
            "请仔细查看这张图片，然后逐字逐句地告诉我图片中的所有文字内容。"
            "如果有公式，也请用文本形式写出来。"
            "不要总结，直接原样转录你能看到的文字。"
        )},
        {
            "type": "image_url",
            "image_url": {"url": data_url, "detail": "high"}
        }
    ]

    logger.info(f"\n{'='*80}")
    logger.info(f"测试 (无工具, 直接对话): {object_name}")
    logger.info(f"{'='*80}")

    response = model.chat(
        system="你是一个 OCR 助手。请原样转录图片中的文字，不要编造。",
        history=[{"role": "user", "content": content_parts}],
        gen_conf={"temperature": 0.1}
    )

    return response


def list_available_images():
    """列出 MinIO 中可用的图片"""
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

    buckets = minio_client.list_buckets()
    logger.info("可用的 Buckets:")
    for bucket in buckets:
        logger.info(f"  - {bucket.name}")

    # 列出第一个 bucket 中的对象
    if buckets:
        first_bucket = buckets[0].name
        logger.info(f"\nBucket '{first_bucket}' 中的对象 (前 20 个):")
        objects = list(minio_client.list_objects(first_bucket, recursive=True))
        for obj in objects[:20]:
            logger.info(f"  - {obj.object_name} ({obj.size} bytes)")


if __name__ == '__main__':
    print("=" * 80)
    print("VLM 图片视觉能力测试")
    print("=" * 80)

    # Step 1: 列出可用图片
    print("\n[Step 1] 检查 MinIO 中的可用图片...")
    try:
        list_available_images()
    except Exception as e:
        logger.warning(f"无法列出 MinIO 图片: {e}")
        print("请确保 MinIO 服务正在运行 (docker-compose up minio)")

    # Step 2: 自动发现测试图片
    # 从第一个 bucket 中取前几张图片
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    buckets = minio_client.list_buckets()
    if not buckets:
        print("❌ 没有可用 Bucket")
        sys.exit(1)

    # 使用第一个有 pages 子目录的 bucket
    test_images = []
    for bucket in buckets:
        objects = list(minio_client.list_objects(bucket.name, recursive=True))
        jpg_objs = [o for o in objects if o.object_name.endswith('.jpg')]
        for obj in jpg_objs[:3]:  # 取前 3 张
            test_images.append(f"minio://{bucket.name}/{obj.object_name}")
        if test_images:
            break

    if not test_images:
        print("❌ 没有找到任何图片")
        sys.exit(1)

    print(f"\n[Step 2] 获取测试图片...")
    image_infos = []
    for img_path in test_images:
        info = get_image_base64_from_minio(img_path)
        if info:
            image_infos.append(info)
        else:
            logger.warning(f"跳过: {img_path}")

    if not image_infos:
        print("\n❌ 没有可用图片，请检查 MinIO 中的图片路径")
        sys.exit(1)

    print(f"\n✅ 成功获取 {len(image_infos)} 张图片")

    # Step 3: 初始化模型
    print(f"\n[Step 3] 初始化 VLM 模型: {MODEL_NAME}")
    model = OpenAI_APIChat(API_KEY, model_name=MODEL_NAME, base_url=BASE_URL)
    print("✅ 模型初始化完成")

    # Step 4: 运行测试
    print(f"\n[Step 4] 开始测试...")

    # 测试 1: 带工具调用的图片理解 (第一张图片)
    print("\n" + "🔍" * 40)
    print("测试 A: Tool Call 模式 — 模型是否能用 tool 提取图片内容？")
    print("🔍" * 40)

    result_a = test_tool_call_with_image(model, image_infos[0], "Tool Call 模式")

    print("\n--- 原始响应 ---")
    print(json.dumps(result_a, ensure_ascii=False, indent=2))

    if result_a.get("tool_calls"):
        print("\n✅ 模型调用了工具！")
        for tc in result_a["tool_calls"]:
            print(f"\n  工具名: {tc['function']['name']}")
            print(f"  参数:")
            try:
                args = json.loads(tc['function']['arguments'])
                print(f"    page_title: {args.get('page_title', 'N/A')}")
                print(f"    language: {args.get('language', 'N/A')}")
                print(f"    main_text (前 300 字): {args.get('main_text', '')[:300]}...")
                print(f"    formulas: {args.get('formulas', [])}")
                print(f"    has_table: {args.get('has_table', False)}")
                print(f"    has_diagram: {args.get('has_diagram', False)}")
                print(f"    diagram_description: {args.get('diagram_description', 'N/A')}")
                print(f"    summary: {args.get('summary', 'N/A')}")
            except json.JSONDecodeError:
                print(f"    (原始): {tc['function']['arguments']}")
    else:
        print("\n⚠️  模型没有调用工具，返回纯文本:")
        print(f"  content: {result_a.get('content', '')[:500]}")
        if result_a.get("reasoning_content"):
            print(f"  reasoning: {result_a.get('reasoning_content', '')[:500]}")

    # 测试 2: 无工具直接对话 (第二张图片，如果存在)
    if len(image_infos) > 1:
        print("\n" + "📝" * 40)
        print("测试 B: 纯对话模式 — 无工具，让模型直接描述图片")
        print("📝" * 40)

        result_b = test_simple_chat_with_image(model, image_infos[1])
        print("\n--- 模型回复 ---")
        print(result_b[:1000] if result_b else "(空)")

    # 总结
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    print("\n💡 判断标准:")
    print("  1. 如果 tool_calls 中提取了具体文字 → 模型能'看到'图片内容")
    print("  2. 如果 main_text 为空或明显不对 → 模型可能只看了个大概，没有真正 OCR")
    print("  3. 如果完全没有 tool_call → 模型可能不支持在带图片时调用工具")
    print("  4. 对比测试 A 和测试 B 的结果，判断 tool 是否影响了视觉能力")
