import binascii
import logging
import re
import time
import base64
import requests
from io import BytesIO
from copy import deepcopy
from timeit import default_timer as timer

from api import settings
from api.db import LLMType, ParserType, StatusEnum
from api.db.db_models import DB, Dialog
from api.db.services.common_service import CommonService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle, TenantLLMService
from rag.app.resume import forbidden_select_fields4resume
from rag.app.tag import label_question
from rag.nlp.search import index_name
from rag.prompts import chunks_format, citation_prompt, kb_prompt, keyword_extraction, llm_id2llm_type, message_fit_in
from rag.utils import num_tokens_from_string, rmSpace

from .database import MINIO_CONFIG, get_minio_client


class DialogService(CommonService):
    model = Dialog

    @classmethod
    @DB.connection_context()
    def get_list(cls, tenant_id, page_number, items_per_page, orderby, desc, id, name):
        chats = cls.model.select()
        if id:
            chats = chats.where(cls.model.id == id)
        if name:
            chats = chats.where(cls.model.name == name)
        chats = chats.where((cls.model.tenant_id == tenant_id) & (cls.model.status == StatusEnum.VALID.value))
        if desc:
            chats = chats.order_by(cls.model.getter_by(orderby).desc())
        else:
            chats = chats.order_by(cls.model.getter_by(orderby).asc())

        chats = chats.paginate(page_number, items_per_page)

        return list(chats.dicts())


def get_image_base64_from_minio(image_path):
    """
    从MinIO获取图片并转换为base64编码

    参数:
        image_path: MinIO中的图片路径，格式为 "minio://bucket/path/to/image.jpg"

    返回:
        base64编码的图片数据URL，格式为 "data:image/jpeg;base64,..."
        如果失败返回None
    """
    print('从minio中检索的的图片的url')
    print(image_path)
    try:
        # 获取MinIO客户端
        minio_client = get_minio_client()

        # 解析bucket和object路径
        # image_path格式：minio://bucket/path/to/image.jpg
        if image_path.startswith("minio://"):
            # 移除协议前缀
            path_without_protocol = image_path[8:]  # 移除 "minio://"
            parts = path_without_protocol.split('/', 1)
            if len(parts) != 2:
                logging.error(f"Invalid image path format: {image_path}")
                return None
            bucket_name = parts[0]  # 例如：a6ca6fbcf2eb11f09fbd420839d2c599
            object_name = parts[1]  # 例如：53c7c8a2f50a11f0b722420839d2c59b/pages/0002.jpg
        else:
            # 兼容旧格式（不带协议前缀）
            parts = image_path.split('/', 1)
            if len(parts) != 2:
                logging.error(f"Invalid image path format: {image_path}")
                return None
            bucket_name = parts[0]
            object_name = parts[1]

        print(f"Bucket: {bucket_name}, Object: {object_name}")

        # 从MinIO获取图片数据
        response = minio_client.get_object(bucket_name, object_name)
        image_data = response.read()
        response.close()
        response.release_conn()

        # 转换为base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # 根据文件扩展名确定MIME类型
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

        # 构建data URL
        data_url = f"data:{mime_type};base64,{base64_image}"

        logging.info(f"成功从MinIO获取图片并转换为base64: {image_path} (大小: {len(image_data)} bytes)")
        return data_url

    except Exception as e:
        logging.error(f"从MinIO获取图片失败: {image_path}, 错误: {str(e)}")
        return None


def _recognize_intent(chat_mdl, messages) -> str:
    """
    意图识别：判断用户最后一条消息是否需要检索知识库。

    返回:
        'knowledge_query' — 需要检索知识库来回答
        'chitchat' — 闲聊、打招呼、感谢等日常对话
        'meta_question' — 询问系统能力或身份
    """
    system_prompt = """你是一个意图分类器。分析对话中用户最后一条消息的类型，只输出一个标签。

标签定义：
- knowledge_query：需要检索文档/知识库来回答的问题，包括对概念的解释、对知识的提问、对流程的询问等
- chitchat：日常闲聊、打招呼、感谢、同意、表示情绪等（如"你好""谢谢""好的""哈哈""OK"）
- meta_question：询问系统能力或身份的问题（如"你能做什么""你是谁""你是什么模型""你会什么"）

只输出一个标签名（如 knowledge_query），不要任何其他内容。"""

    # 将历史对话和当前问题剥离开来
    # history_msgs: 当前问题之前的对话上下文，用于理解指代和省略
    # current_question: 用户最后一条消息，即待分类的目标问题
    all_msgs = [m for m in messages if m["role"] != "system"]
    history_msgs = all_msgs[:-1]  # 去掉最后一条（当前问题）
    current_question = all_msgs[-1]["content"] if all_msgs else ""

    # 显式组装：历史上下文 + 当前问题，避免 LLM 把分类任务当成对话回复
    # 取最近 6 条历史消息（3 轮完整对话，user + assistant 各一轮），保证上下文完整
    if history_msgs:
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history_msgs[-6:]])
        user_msg = f"对话历史：\n{history_text}\n\n当前问题：{current_question}\n\n请对上述「当前问题」进行意图分类。"
    else:
        user_msg = f"当前问题：{current_question}\n\n请对上述「当前问题」进行意图分类。"

    try:
        result = chat_mdl.chat(system_prompt, [{"role": "user", "content": user_msg}], {"temperature": 0.0, "max_tokens": 32})
        result = result.strip().lower()
        logging.info(f"[INTENT] Raw result: '{result}'")

        if "knowledge" in result:
            return "knowledge_query"
        elif "chitchat" in result or "chat" in result:
            return "chitchat"
        elif "meta" in result:
            return "meta_question"
        else:
            logging.warning(f"[INTENT] Unrecognized label '{result}', defaulting to knowledge_query")
            return "knowledge_query"
    except Exception as e:
        logging.error(f"[INTENT] Intent recognition failed: {e}, defaulting to knowledge_query")
        return "knowledge_query"


def chat_solo(dialog, messages, stream=True):
    # 初始化一个聊天模型，这个模型不仅仅有对话的能力，还有多模态的能力，我只需要把图片的base64传递到message里面即可。
    chat_mdl = LLMBundle(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)
    system_prompt = "你是一个有用的AI助手, 你的名字叫做灵机AI。"
    llm_setting = {"temperature": 0.1, "top_p": 0.3, "presence_penalty": 0.4, "frequency_penalty": 0.7}
    msg = [{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} for m in messages if m["role"] != "system"]
    if stream:
        last_ans = ""
        for ans in chat_mdl.chat_streamly(system=system_prompt, history=msg, gen_conf=llm_setting):
            answer = ans
            delta_ans = ans[len(last_ans) :]
            if num_tokens_from_string(delta_ans) < 4:
                continue
            last_ans = answer
            yield {"answer": answer, "reference": {}}
        if delta_ans:
            yield {"answer": answer, "reference": {}}


def chat(dialog, messages, stream=True, **kwargs):
    """
    dialog:数据库表里面的dialog信息
    messages:message列表，只包含id、role、content这样一种的dict列表
    """
    assert messages[-1]["role"] == "user", "The last content of this conversation is not from user."
    if not dialog.kb_ids:
        for ans in chat_solo(dialog, messages, stream):
            yield ans
        return
    # TODO：上面那种对话，还是文本形式的对话，并没有考虑上传图片、上传文件的问答情况。之后可以添加

    # ===================
    # 第一步：获取到租户的聊天模型
    # ===================
    chat_mdl = LLMBundle(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)

    # ===================
    # 第二步：意图识别 — 判断用户问题是否需要检索知识库
    # 闲聊/打招呼/询问系统能力等，直接走 LLM 对话，节省检索资源
    # ===================
    intent = _recognize_intent(chat_mdl, messages)
    if intent != "knowledge_query":
        logging.info(f"[CHAT] Intent is '{intent}', skipping retrieval, using chat_solo")
        for ans in chat_solo(dialog, messages, stream):
            yield ans
        return

    logging.info("[CHAT] Intent is 'knowledge_query', proceeding with retrieval")

    # ===================
    # 第三步：获取到知识库配置的embedding模型。本质上来说只会有一个embedding模型，因为我把接口隐藏了
    # dialog配备知识库，dialog配备llm、rerank，而配置embedding模型的是知识库，不同的知识库可以配置不同的embedding模型
    # 当然这里做了一个判断，一个dialog如果享有多个知识库，这些知识库配置的embedding模型必须是相同的
    # ===================
    kbs = KnowledgebaseService.get_by_ids(dialog.kb_ids)
    embedding_list = list(set([kb.embd_id for kb in kbs]))
    if len(embedding_list) != 1:
        yield {"answer": "**ERROR**: Knowledge bases use different embedding models.", "reference": {}}
        return {"answer": "**ERROR**: Knowledge bases use different embedding models.", "reference": {}}
    embedding_model_name = embedding_list[0]
    embd_mdl = LLMBundle(dialog.tenant_id, LLMType.EMBEDDING, embedding_model_name)
    if not embd_mdl:
        raise LookupError("Embedding model(%s) not found" % embedding_model_name)
    
    # ===================
    # 第四步：初始化一个es的检索器
    # ===================
    retriever = settings.retrievaler

    # 调试：打印对话信息
    logging.info(f"[CHAT DEBUG] Dialog ID: {dialog.id}")
    logging.info(f"[CHAT DEBUG] 模型ID: {dialog.llm_id}")
    logging.info(f"[CHAT DEBUG] LLM设置: {dialog.llm_setting}")

    # ===================
    # 第五步：获取到用户的最近的问题
    # ===================
    questions = [m["content"] for m in messages if m["role"] == "user"][-3:]
    questions = questions[-1:]

    # ===================
    # 第六步：获取到一个rerank模型（可选）
    # ===================
    rerank_mdl = None
    if dialog.rerank_id:
        rerank_mdl = LLMBundle(dialog.tenant_id, LLMType.RERANK, dialog.rerank_id)

    # 获取 dialog 的 prompt_config
    prompt_config = dialog.prompt_config

    # ===================
    # 第七步：通过retrieval检索器的召回，来召回对应的一些文档或者文档截图，返回类似的下面这样一个结果
    # kbinfos = {"total": 0, "chunks": []}
    # 然后再组装一下prompt
    # ===================
    thought = ""
    kbinfos = {"total": 0, "chunks": []}
    tenant_ids = list(set([kb.tenant_id for kb in kbs])) # 当前的用户只能使用当前租户的embedding、llm、rerank。但是呢，这个dialog享有的不同知识库，可能是不同的租户的，别的租户给我开放权限
    knowledges = []

    # 检索模式选择
    use_page_vector_retrieval = "page_vector"  # 临时设置为使用页面向量检索

    if use_page_vector_retrieval == "page_vector":
        # 单纯只使用图片向量进行检索
        """
        进入检索之前
        ['介绍一下Qwen3-VL-Embedding and Qwen3-VL-Reranker:']
        ['5b909f6cf2eb11f0946f420839d2c599']
        ['fab5201fe75041a3be982fa57af16745']
        """
        # 方案一：粗排 + 精排：使用 rerank 模型重排序
        # kbinfos = retriever.page_vector_retrieval(
        #     " ".join(questions), # 用户的原始问题
        #     embd_mdl, # embedding模型
        #     tenant_ids, # 知识库的所属租户id。也就是需要检索哪些es索引
        #     dialog.kb_ids, # 单个es索引下，我要检索哪些范围
        #     rerank_mdl, # rerank模型，用于重排序
        #     top_k=2, # 返回的页面数量（Top 2）。最终返回2张页面
        #     similarity_threshold=0.1, # 相似度阈值。只要页面的相似度>0.1的都召回
        #     retrieval_top_k=4 # 向量检索的候选数量（Top 4），用于 rerank 重排序
        # )
        # kbinfos 格式: {"total": N, "chunks": [{"page_id", "doc_id", "img_url", ...}]}
        # 精排。原来的那个版本是把这个重排许模型传到了那个retriever函数的retrieval中
        
        # 方案二：文本、图片、关键词（并行召回）,进行混合检索
        kbinfos = retriever.hybrid_page_retrieval(
            question=" ".join(questions),
            embd_mdl=embd_mdl,
            tenant_ids=tenant_ids,
            kb_ids=dialog.kb_ids,
            rerank_mdl=rerank_mdl,
            chat_mdl=chat_mdl,
            # 使用合理的默认值
            image_topk=50,
            text_topk=50,
            keyword_topk=50,
            rrf_k=60,
            rrf_topk=5,
            rerank_final_topk=3,
            similarity_threshold=0.7, # 这里的阈值是给最后一阶段rerank模型进行使用的
            enable_context_recall=True, # 是否开启上下页召回
            context_recall_max_pages=1
        )


    # ====================
    # 把检索到的信息组装成大模型可用的格式
    # ====================
    # knowledges = kb_prompt(kbinfos)

    # kwargs["knowledge"] = "\n------\n" + "\n\n------\n\n".join(knowledges)
    gen_conf = {"temperature": 0.1, "top_p": 0.3, "presence_penalty": 0.4, "frequency_penalty": 0.7}
    system_prompt = "你是一个有用的AI助手，负责根据用户的文档截图回答用户的问题。"
    msg = [] # 用户的历史对话
    msg.extend([{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} for m in messages if m["role"] != "system"])

    page_images = []

    # 在这里拼接上了用户的query与检索到的图片
    if use_page_vector_retrieval == "page_vector" and kbinfos.get("chunks"):
        logging.info(f"纯页面向量检索模式：找到 {len(kbinfos.get('chunks', []))} 个相关页面")

        # 提取所有页面的图片路径
        for chunk in kbinfos["chunks"]:
            img_url = chunk.get("img_url", "")
            if img_url:
                # img_url 格式: minio://bucket/path/to/image.jpg
                page_images.append(img_url)

        logging.info(f"页面图片列表: {page_images}")

        # 如果有图片，将图片转换为base64并添加到用户消息中
        if page_images:
            logging.info(f"页面检索模式：找到 {len(page_images)} 张页面图片，将转换为base64并传递给VLM模型")

            # 修改最后一条用户消息，添加图片内容
            if msg and msg[-1]["role"] == "user":
                # 构建多模态消息格式（OpenAI Vision API格式）
                user_text = msg[-1]["content"]
                content_parts = [{"type": "text", "text": user_text}]

                # 转换图片为base64并添加（限制最多3张，避免token过多）
                successful_images = 0
                for img_path in page_images:
                    # 从MinIO获取图片并转换为base64
                    base64_data_url = get_image_base64_from_minio(img_path)

                    if base64_data_url:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": base64_data_url,  # 使用base64 data URL
                                "detail": "auto"
                            }
                        })
                        successful_images += 1
                    else:
                        logging.warning(f"跳过无法获取的图片: {img_path}")

                if successful_images > 0:
                    msg[-1]["content"] = content_parts
                    logging.info(f"已将 {successful_images} 张图片转换为base64并添加到用户消息中")
                else:
                    logging.warning("所有图片获取失败，将使用纯文本模式")
    else:
        pass  # 不需要做任何处理


    # 这个函数是用来格式化答案的
    def decorate_answer(answer):
        refs = []

        # 纯页面向量检索模式的特殊处理
        if use_page_vector_retrieval == "page_vector":
            # 直接返回检索到的页面信息，不进行引用标注
            refs = {
                "total": kbinfos.get("total", 0),
                "chunks": [],
                "doc_aggs": []
            }

            # 构建页面引用信息（包含图片URL）
            for chunk in kbinfos.get("chunks", []):
                page_ref = {
                    "page_id": chunk.get("page_id", ""),
                    "doc_id": chunk.get("doc_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": chunk.get("similarity", 0.0)
                }

                # 如果 img_url 是 minio:// 格式，转换为 HTTP URL
                img_url = chunk.get("img_url", "")
                if img_url and img_url.startswith("minio://"):
                    # 直接字符串替换，简单高效
                    protocol = "https" if MINIO_CONFIG.get("secure", False) else "http"
                    page_ref["img_url"] = img_url.replace("minio://", f"{protocol}://{MINIO_CONFIG['visit_point']}/")
                
                # 只把主页面添加进去
                if not chunk.get("is_context", False): refs["chunks"].append(page_ref)

            # 文档聚合信息（只聚合主文档，不包括上下文页面）
            doc_dict = {}
            for chunk in kbinfos.get("chunks", []):
                # 跳过上下文页面
                if chunk.get("is_context", False):
                    continue
                doc_id = chunk.get("doc_id", "")
                doc_name = chunk.get("docnm_kwd", "")
                if doc_id and doc_name:
                    if doc_id not in doc_dict:
                        doc_dict[doc_id] = {"doc_id": doc_id, "doc_name": doc_name, "count": 0}
                    doc_dict[doc_id]["count"] += 1

            refs["doc_aggs"] = list(doc_dict.values())

            return {
                "answer": answer,
                "reference": refs
            }

        # 原有的处理逻辑（chunk 检索模式）
        ans = answer.split("</think>")
        think = ""
        if len(ans) == 2:
            think = ans[0] + "</think>"
            answer = ans[1]

        cited_chunk_indices = set()
        inserted_images = {}
        processed_image_urls = set()

        if knowledges and (prompt_config.get("quote", True) and kwargs.get("quote", True)):
            # 获取引用的 chunk 索引
            if not re.search(r"##[0-9]+\$\$", answer):
                answer, idx = retriever.insert_citations(
                    answer,
                    [ck["content_ltks"] for ck in kbinfos["chunks"]],
                    [ck["vector"] for ck in kbinfos["chunks"]],
                    embd_mdl,
                    tkweight=1 - dialog.vector_similarity_weight,
                    vtweight=dialog.vector_similarity_weight,
                )
                cited_chunk_indices = idx
            else:
                for r in re.finditer(r"##([0-9]+)\$\$", answer):
                    i = int(r.group(1))
                    if i < len(kbinfos["chunks"]):
                        cited_chunk_indices.add(i)

            # 处理图片插入
            def insert_image_markdown(match):
                idx = int(match.group(1))
                if idx >= len(kbinfos["chunks"]):
                    return match.group(0)

                chunk = kbinfos["chunks"][idx]
                img_path = chunk.get("image_id")
                if not img_path:
                    return match.group(0)

                protocol = "https" if MINIO_CONFIG.get("secure", False) else "http"
                img_url = f"{protocol}://{MINIO_CONFIG['visit_point']}/{img_path}"

                if img_url in processed_image_urls:
                    return match.group(0)

                processed_image_urls.add(img_url)
                inserted_images[idx] = img_url

                # 插入图片，并限制最大宽度
                return f'{match.group(0)}\n\n<img src="{img_url}" alt="{img_url}" style="max-width:800px;">'

            # 用正则替换插图
            answer = re.sub(r"##(\d+)\$\$", insert_image_markdown, answer)

            # 清理引用文献信息
            idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in cited_chunk_indices])
            recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
            if not recall_docs:
                recall_docs = kbinfos["doc_aggs"]
            kbinfos["doc_aggs"] = recall_docs

            refs = deepcopy(kbinfos)
            
            # 为前端构建完整的图片URL
            for c in refs["chunks"]:
                if c.get("vector"):
                    del c["vector"]
                
                # 如果是页面类型且有图片路径，构建完整的MinIO URL
                if c.get("doc_type_kwd") == "page" and c.get("image_id"):
                    img_path = c.get("image_id")
                    # 如果不是完整URL，构建完整URL
                    if img_path and not img_path.startswith("http"):
                        protocol = "https" if MINIO_CONFIG.get("secure", False) else "http"
                        c["image_id"] = f"{protocol}://{MINIO_CONFIG['visit_point']}/{img_path}"

        # 特殊错误提示
        if "invalid key" in answer.lower() or "invalid api" in answer.lower():
            answer += " Please set LLM API-Key in 'User Setting -> Model providers -> API-Key'"

        return {"answer": think + answer, "reference": refs, "created_at": time.time()}

    if stream:
        last_ans = "" # 这个主要是存储上次返回了什么
        answer = "" # 这个是ans的一个副本

        for ans in chat_mdl.chat_streamly(system_prompt, msg, gen_conf):
            # 我是怎么判断是否存在think标记的？
            # 从来也没有人更新thought啊，这个thought一直都是空的字符串
            if thought:
                ans = re.sub(r"<think>.*</think>", "", ans, flags=re.DOTALL)
            answer = ans
            delta_ans = ans[len(last_ans) :]
            if num_tokens_from_string(delta_ans) < 4:
                continue
            last_ans = answer
            # 返回当前累计回答(包含思考过程)+新增片段)
            yield {"answer": thought + answer, "reference": {}}
        delta_ans = answer[len(last_ans): ]
        if delta_ans:
            yield {"answer": thought + answer, "reference": {}}
        yield decorate_answer(thought + answer)


def ask(question, kb_ids, tenant_id):
    """
    处理用户搜索请求，从知识库中检索相关信息并生成回答

    参数:
        question (str): 用户的问题或查询
        kb_ids (list): 知识库ID列表，指定要搜索的知识库
        tenant_id (str): 租户ID，用于权限控制和资源隔离

    流程:
        1. 获取指定知识库的信息
        2. 确定使用的嵌入模型
        3. 根据知识库类型选择检索器(普通检索器或知识图谱检索器)
        4. 初始化嵌入模型和聊天模型
        5. 执行检索操作获取相关文档片段
        6. 格式化知识库内容作为上下文
        7. 构建系统提示词
        8. 生成回答并添加引用标记
        9. 流式返回生成的回答

    返回:
        generator: 生成器对象，产生包含回答和引用信息的字典
    """

    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    embedding_list = list(set([kb.embd_id for kb in kbs]))

    is_knowledge_graph = all([kb.parser_id == ParserType.KG for kb in kbs])
    retriever = settings.retrievaler if not is_knowledge_graph else settings.kg_retrievaler
    # 初始化嵌入模型，用于将文本转换为向量表示
    embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, embedding_list[0])
    # 初始化聊天模型，用于生成回答
    chat_mdl = LLMBundle(tenant_id, LLMType.CHAT)
    # 获取所有知识库的租户ID并去重
    tenant_ids = list(set([kb.tenant_id for kb in kbs]))
    # 设置更小的相似度阈值以适配更好的效果(原始值0.1)
    similarity_threshold = 0.01
    # 调用检索器检索相关文档片段
    kbinfos = retriever.retrieval(question, embd_mdl, tenant_ids, kb_ids, 1, 12, similarity_threshold, 0.3, aggs=False, rank_feature=label_question(question, kbs))
    # 将检索结果格式化为提示词
    knowledges = kb_prompt(kbinfos)
    prompt = """
    角色：你是一个聪明的助手。  
    任务：总结知识库中的信息并回答用户的问题。  
    要求与限制：
    - 绝不要捏造内容，尤其是数字。
    - 如果知识库中的信息与用户问题无关，**只需回答：对不起，未提供相关信息。
    - 使用Markdown格式进行回答。
    - 使用用户提问所用的语言作答。
    - 绝不要捏造内容，尤其是数字。

    ### 来自知识库的信息
    %s

    以上是来自知识库的信息。

    """ % "\n".join(knowledges)
    msg = [{"role": "user", "content": question}]

    # 生成完成后添加回答中的引用标记
    def decorate_answer(answer):
        nonlocal knowledges, kbinfos, prompt
        answer, idx = retriever.insert_citations(answer, [ck["content_ltks"] for ck in kbinfos["chunks"]], [ck["vector"] for ck in kbinfos["chunks"]], embd_mdl, tkweight=0.7, vtweight=0.3)
        idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
        recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
        if not recall_docs:
            recall_docs = kbinfos["doc_aggs"]
        kbinfos["doc_aggs"] = recall_docs
        refs = deepcopy(kbinfos)
        for c in refs["chunks"]:
            if c.get("vector"):
                del c["vector"]

        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model Providers -> API-Key'"
        refs["chunks"] = chunks_format(refs)
        return {"answer": answer, "reference": refs}

    answer = ""
    for ans in chat_mdl.chat_streamly(prompt, msg, {"temperature": 0.1}):
        answer = ans
        yield {"answer": answer, "reference": {}}
    yield decorate_answer(answer)
