from abc import ABC
from openai import OpenAI
import openai
from rag.nlp import is_chinese
import os
import mimetypes
import base64
import logging
import uuid
import json
import re

logger = logging.getLogger('ragflow.llm.chat_model')

LENGTH_NOTIFICATION_CN = "······\n由于大模型的上下文窗口大小限制，回答已经被大模型截断。"
LENGTH_NOTIFICATION_EN = "...\nThe answer is truncated by your chosen LLM due to its limitation on context length."


class Base(ABC):
    def __init__(self, key, model_name, base_url):
        timeout = int(os.environ.get('LM_TIMEOUT_SECONDS', 600))
        self.client = openai.OpenAI(api_key=key, base_url=base_url, timeout=timeout)
        self.model_name = model_name

    def _build_messages(self, system, history):
        messages = history.copy()  # 浅拷贝
        if system:
            messages.insert(0, {"role": "system", "content": system})
        return messages

    def chat(self, system, history, gen_conf=None):
        if gen_conf is None:
            gen_conf = {}
        messages = self._build_messages(system, history)
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **gen_conf)
            if not response.choices:
                return ""
            
            ans = ""
            message = response.choices[0].message

            # 直接取 content 回复，不包含 reasoning_content
            # reasoning_content（<think> 标签）会干扰下游的 JSON 解析和关键词匹配，
            # 需要 reasoning 的场景使用 chat_streamly（流式接口会保留）
            if message.content:
                ans += message.content.strip()
            
            # finish_reason：
            # stop：即正常终止   length：因为输出过长被阶段了   tool_calls：模型说要调用工具
            if response.choices[0].finish_reason == "length":
                if is_chinese(ans):
                    ans += LENGTH_NOTIFICATION_CN
                else:
                    ans += LENGTH_NOTIFICATION_EN
            return ans
            
        except openai.APIError as e:
            return "**ERROR**: " + str(e)

    def chat_streamly(self, system, history, gen_conf=None):
        if gen_conf is None:
            gen_conf = {}

        messages = self._build_messages(system, history)
        ans = ""
        is_reasoning = False # 新增：用于追踪当前是否处于思考阶段
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **gen_conf,
                stream=True)

            for resp in response:
                if not resp.choices:
                    continue
                delta = resp.choices[0].delta

                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    if "<think>" not in ans:
                        ans += "<think>\n"
                    # 先加上去掉上次的假的闭合标签，在加上本次的闭合标签
                    ans = ans.replace("\n</think>", "")
                    ans += delta.reasoning_content + "\n</think>"

                if delta.content:
                    ans += delta.content

                if resp.choices[0].finish_reason == "length":
                    if is_chinese(ans):
                        ans += LENGTH_NOTIFICATION_CN
                    else:
                        ans += LENGTH_NOTIFICATION_EN
                yield ans

        except openai.APIError as e:
            yield ans + "\n**ERROR**: " + str(e)

    def chat_with_tools(self, system, history, gen_conf=None):
        """
        支持工具调用的聊天方法（兼容标准格式与文本泄漏格式）
        """
        if gen_conf is None:
            gen_conf = {}

        messages = self._build_messages(system, history)

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **gen_conf
            )
            

            if not response.choices:
                return {"content": "", "reasoning_content": "", "tool_calls": None}
            
            message = response.choices[0].message
            result = {
                "content": message.content or "",
                "reasoning_content": getattr(message, "reasoning_content", "") or "",
                "tool_calls": None
            }

            # ---------------------------------------------------------
            # 第一道防线：提取标准的 Tool Calls（针对 GPT-4o 等乖巧模型）
            # ---------------------------------------------------------
            if hasattr(message, "tool_calls") and message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments 
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            # ---------------------------------------------------------
            # 第二道防线：正则兜底提取（针对 Qwen、DeepSeek 等淘气模型）
            # ---------------------------------------------------------
            else:
                # 将思考内容和正文拼接在一起搜索，防止漏网之鱼
                search_text = f"{result['reasoning_content']}\n{result['content']}"
                
                # 匹配所有 <tool_call> ... </tool_call> 标签块
                pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
                matches = re.finditer(pattern, search_text, re.DOTALL)
                
                extracted_tools = []
                for match in matches:
                    json_str = match.group(1)
                    try:
                        tool_data = json.loads(json_str)
                        
                        # 获取参数并强制转回 JSON 字符串！
                        # 为什么？因为标准 OpenAI API 的 arguments 是字符串格式，
                        # 你的上层业务代码一定是用 json.loads() 去解析 arguments 的。
                        raw_args = tool_data.get("arguments", {})
                        args_string = json.dumps(raw_args, ensure_ascii=False) if isinstance(raw_args, dict) else str(raw_args)

                        extracted_tools.append({
                            # 伪造一个唯一的 tool_call_id，保证后续提交工具结果时不出错
                            "id": f"call_extracted_{uuid.uuid4().hex[:8]}", 
                            "type": "function",
                            "function": {
                                "name": tool_data.get("name", ""),
                                "arguments": args_string
                            }
                        })
                    except json.JSONDecodeError:
                        print(f"**警告**: 发现 <tool_call> 标签，但 JSON 解析失败：\n{json_str}")
                        continue
                
                if extracted_tools:
                    result["tool_calls"] = extracted_tools


            # 处理长度截断提示
            if response.choices[0].finish_reason == "length":
                if is_chinese(result["content"]):
                    result["content"] += LENGTH_NOTIFICATION_CN
                else:
                    result["content"] += LENGTH_NOTIFICATION_EN

            return result

        except openai.APIError as e: 
            return {"content": "**ERROR**: " + str(e), "reasoning_content": "", "tool_calls": None}
        
class OpenAI_APIChat(Base):
    def __init__(self, key, model_name, base_url):
        if not base_url:
            raise ValueError("url cannot be None")
        model_name = model_name.split("___")[0]
        super().__init__(key, model_name, base_url)

if __name__ == '__main__':
    # 导入 MinIO 客户端
    try:
        from minio import Minio
    except ImportError:
        print("请先安装 minio 库: pip install minio")
        exit(1)

    def get_image_base64_from_minio(image_path):
        """
        从 MinIO 获取图片并转换为 base64 编码的 Data URL

        参数:
            image_path: MinIO 中的图片路径，格式为 "minio://bucket/path/to/image.jpg"
        """
        print(f'正在从 MinIO 获取图片: {image_path}')

        try:
            # MinIO 配置 (根据实际情况修改)
            MINIO_ENDPOINT = "localhost:9000"  # 或者 "localhost:9000"
            MINIO_ACCESS_KEY = "rag_flow"
            MINIO_SECRET_KEY = "infini_rag_flow"
            MINIO_SECURE = False  # 如果使用 HTTPS，设置为 True

            # 初始化 MinIO 客户端
            minio_client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE
            )

            # 解析 bucket 和 object 路径
            if image_path.startswith("minio://"):
                # 移除协议前缀
                path_without_protocol = image_path[8:]  # 移除 "minio://"
                parts = path_without_protocol.split('/', 1)
                if len(parts) != 2:
                    print(f"❌ 无效的图片路径格式: {image_path}")
                    return None
                bucket_name = parts[0]
                object_name = parts[1]
            else:
                print(f"❌ 不支持的图片路径格式: {image_path}")
                return None

            print(f"  Bucket: {bucket_name}, Object: {object_name}")

            # 从 MinIO 获取图片数据
            response = minio_client.get_object(bucket_name, object_name)
            image_data = response.read()
            response.close()
            response.release_conn()

            # 转换为 base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # 根据文件扩展名确定 MIME 类型
            ext = object_name.lower().split('.')[-1]
            mime_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'bmp': 'image/bmp'
            }
            mime_type = mime_type_map.get(ext, 'image/jpeg')

            # 构建 data URL
            data_url = f"data:{mime_type};base64,{base64_image}"
            print(f"✅ 成功获取并转换图片 (大小: {len(image_data)} bytes)")
            return data_url

        except Exception as e:
            print(f"❌ 从 MinIO 获取图片失败: {str(e)}")
            return None

    # ========== 测试代码 ==========
    print("=" * 80)
    print("测试 VLM 模型调用（从 MinIO 获取多张图片）")
    print("=" * 80)

    # MinIO 图片列表
    minio_images = [
        'minio://502b3174fd1711f0bc0e420839d2c59b/5144a194fd1711f0bc0e420839d2c59b/pages/0007.jpg',
        'minio://502b3174fd1711f0bc0e420839d2c59b/5144a194fd1711f0bc0e420839d2c59b/pages/0008.jpg',
        'minio://502b3174fd1711f0bc0e420839d2c59b/5144a194fd1711f0bc0e420839d2c59b/pages/0009.jpg',
    ]

    print(f"\n[步骤1] 从 MinIO 获取 {len(minio_images)} 张图片...")
    image_data_urls = [] # 这里存储的都是base64
    for img_path in minio_images:
        data_url = get_image_base64_from_minio(img_path)
        if data_url:
            image_data_urls.append(data_url)
        else:
            print(f"⚠️  跳过无法获取的图片: {img_path}")

    if not image_data_urls:
        print("\n❌ 没有成功获取到任何图片，退出测试")
        exit(1)

    print(f"\n✅ 成功获取 {len(image_data_urls)} 张图片")

    # 初始化 VLM 模型
    print(f"\n[步骤2] 初始化 VLM 模型...")
    openai_api = OpenAI_APIChat(
        'sk-ddmuwiogctbqpznflymvdrdbasdelejzahfhickpovhlcpzr',
        model_name='Qwen/Qwen3-VL-32B-Instruct',
        base_url='https://api.siliconflow.cn/v1'
    )
    print(f"✅ 模型初始化完成")


    # ========== 测试 chat_with_tools ==========
    print("\n" + "=" * 80)
    print("测试 chat_with_tools（工具调用）")
    print("=" * 80)

    # 定义工具
    tools = [{
        "type": "function",
        "function": {
            "name": "evaluate_page_context",
            "description": "评估页面是否需要前后页上下文信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "is_relevant": {
                        "type": "boolean",
                        "description": "该页面是否包含能回答用户问题的任何相关信息"
                    },
                    "reason": {
                        "type": "string",
                        "description": "判断相关或不相关的简要理由"
                    },
                    "needs_prev_page": {
                        "type": "boolean",
                        "description": "页面信息是否在开头被截断，强烈需要上一页的上下文"
                    },
                    "needs_next_page": {
                        "type": "boolean",
                        "description": "页面信息是否在结尾未讲完，强烈需要下一页的上下文"
                    }
                },
                "required": ["is_relevant", "reason", "needs_prev_page", "needs_next_page"]
            }
        }
    }]

    # 构建多模态消息（第一张图片）
    content_parts = [
        {"type": "text", "text": "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"},
        {
            "type": "image_url",
            "image_url": {"url": image_data_urls[0], "detail": "auto"}
        }
    ]

    print("\n[步骤1] 调用 chat_with_tools...")


    # ========== 测试1: 带图片的工具调用 ==========
    print("\n--- 测试1: 带图片的工具调用 ---")
    response_with_image = openai_api.chat_with_tools(
        system="你是一个智能文档助手。请使用 evaluate_page_context 工具评估页面。",
        history=[{"role": "user", "content": content_parts}],
        gen_conf={
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1
        }
    )
    print(response_with_image)
    print(f"带图片结果: {response_with_image.get('tool_calls')}")

