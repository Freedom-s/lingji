import datetime
import os
import xxhash
import re
from flask import request
from flask_login import login_required, current_user
from rag.app.qa import rmPrefix, beAdoc
from rag.nlp import search, rag_tokenizer
from rag.settings import PAGERANK_FLD
from rag.utils import rmSpace
from api.db import LLMType, ParserType
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api.db.services.user_service import UserTenantService, TenantService
from api.utils.api_utils import server_error_response, get_data_error_result, validate_request
from api.db.services.document_service import DocumentService
from api import settings
from api.utils.api_utils import get_json_result


def convert_minio_url_to_http(img_url: str) -> str:
    """
    将 MinIO URL (minio://bucket/path/to/file.jpg) 转换为 HTTP URL

    参数:
        img_url: MinIO 协议 URL

    返回:
        HTTP URL (http://host:port/bucket/path/to/file.jpg)
    """
    if not img_url or not img_url.startswith("minio://"):
        return img_url

    try:
        # 解析 minio://bucket/path/to/file.jpg
        path_without_protocol = img_url[8:]  # 移除 "minio://"
        parts = path_without_protocol.split('/', 1)
        if len(parts) != 2:
            return img_url

        bucket_name = parts[0]
        object_path = parts[1]

        # 获取 MinIO 访问地址
        host = os.getenv("MINIO_VISIT_HOST", "localhost")
        if not host.startswith("http://") and not host.startswith("https://"):
            host = "http://" + host
        port = os.getenv("MINIO_PORT", "9000")

        # 构建完整的 HTTP URL
        http_url = f"{host}:{port}/{bucket_name}/{object_path}"
        return http_url

    except Exception as e:
        # 转换失败，返回原 URL
        return img_url


@manager.route("/list", methods=["POST"])  # noqa: F821
@login_required
@validate_request("doc_id")
def list_chunk():
    """
    这个接口会返回两个数据回去，一个是chunks、一个是doc
    获取指定文档的页面列表（多模态页面级 RAG）

    请求参数:
        doc_id (str, 必填): 文档 ID
        page (int, 可选): 页码，默认 1
        size (int, 可选): 每页数量，默认 30
        keywords (str, 可选): 搜索关键词

    返回格式:
        {
            "total": int,
            "doc": dict,
            "chunks": [
                {
                    "page_id": str,
                    "doc_id": str,
                    "kb_id": str,
                    "docnm_kwd": str,
                    "content_with_weight": str,
                    "content_ltks": str,
                    "page_num_int": int,
                    "img_url": str,
                    "create_time": str,
                    "create_timestamp_flt": float
                }
            ]
        }
    """
    req = request.json
    doc_id = req["doc_id"]
    page = int(req.get("page", 1))
    size = int(req.get("size", 30))
    question = req.get("keywords", "")

    try:
        # 预检查，查询这个doc_id是属于哪个租户的
        tenant_id = DocumentService.get_tenant_id(doc_id)
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")

        # 查询document表里面的记录
        e, doc = DocumentService.get_by_id(doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")
        
        # 查询这个租户有哪些kb，返回这些kb_ids字段
        kb_ids = KnowledgebaseService.get_kb_ids(tenant_id)
        print('tenant_id:',tenant_id)
        print('kbs:',kb_ids)
        
        # 指定返回字段（ES 中实际存在的字段）
        src_fields = [
            "page_id",
            "doc_id",
            "kb_id",
            "docnm_kwd",
            "content_with_weight",
            "content_ltks",
            "page_num_int",
            "img_url",
            "create_time",
            "create_timestamp_flt",
        ]

        # 构建检索查询
        query = {
            "doc_ids": [doc_id],
            "page": page,
            "size": size,
            "question": question,
            "sort": False,
            "fields": src_fields
        }

        # 执行检索（使用关键字参数避免参数位置错误）
        sres = settings.retrievaler.search(
            req=query,
            idx_names=search.index_name(tenant_id),
            kb_ids=kb_ids,
            highlight=True
        )

        # 构建返回结果
        res = {
            "total": sres.total,
            "chunks": [],
            "doc": doc.to_dict()
        }

        # 添加搜索时的元数据
        if question:
            if sres.keywords:
                res["keywords"] = sres.keywords
            if sres.aggregation:
                res["aggregation"] = sres.aggregation

        # 处理页面列表
        for page_id in sres.ids:
            field = sres.field[page_id]

            # 获取内容（优先使用高亮）
            if question and page_id in sres.highlight:
                content = rmSpace(sres.highlight[page_id])
            else:
                content = field.get("content_with_weight", "")

            # 处理 page_num_int（可能是数组或单个值）
            page_num = field.get("page_num_int", 0)
            if isinstance(page_num, list) and len(page_num) > 0:
                page_num = page_num[0]
            try:
                page_num = int(page_num)
            except (ValueError, TypeError):
                page_num = 0

            # 获取原始 img_url 并转换为 HTTP URL
            original_img_url = field.get("img_url", "")
            http_img_url = convert_minio_url_to_http(original_img_url)

            chunk = {
                "page_id": page_id,
                "doc_id": field.get("doc_id", ""),
                "kb_id": field.get("kb_id", ""),
                "docnm_kwd": field.get("docnm_kwd", ""),
                "content_with_weight": content,
                "content_ltks": field.get("content_ltks", ""),
                "page_num_int": page_num,
                "img_url": http_img_url,
                "create_time": field.get("create_time", ""),
                "create_timestamp_flt": field.get("create_timestamp_flt", 0.0),
            }

            res["chunks"].append(chunk)

        # 按 page_num_int 从小到大排序
        res["chunks"].sort(key=lambda x: x["page_num_int"])

        return get_json_result(data=res)

    except Exception as e:
        if "not_found" in str(e):
            return get_json_result(data=False, message="No page found!", code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


@manager.route("/get", methods=["GET"])  # noqa: F821
@login_required
def get():
    chunk_id = request.args["chunk_id"]
    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        if not tenants:
            return get_data_error_result(message="Tenant not found!")
        for tenant in tenants:
            kb_ids = KnowledgebaseService.get_kb_ids(tenant.tenant_id)
            chunk = settings.docStoreConn.get(chunk_id, search.index_name(tenant.tenant_id), kb_ids)
            if chunk:
                break
        if chunk is None:
            return server_error_response(Exception("Chunk not found"))

        k = []
        for n in chunk.keys():
            if re.search(r"(_vec$|_sm_|_tks|_ltks)", n):
                k.append(n)
        for n in k:
            del chunk[n]

        return get_json_result(data=chunk)
    except Exception as e:
        if str(e).find("NotFoundError") >= 0:
            return get_json_result(data=False, message="Chunk not found!", code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


@manager.route("/set", methods=["POST"])  # noqa: F821
@login_required
@validate_request("doc_id", "chunk_id", "content_with_weight")
def set_chunk():
    req = request.json
    d = {"id": req["chunk_id"], "content_with_weight": req["content_with_weight"]}
    d["content_ltks"] = rag_tokenizer.tokenize(req["content_with_weight"])
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])
    if "important_kwd" in req:
        d["important_kwd"] = req["important_kwd"]
        d["important_tks"] = rag_tokenizer.tokenize(" ".join(req["important_kwd"]))
    if "question_kwd" in req:
        d["question_kwd"] = req["question_kwd"]
        d["question_tks"] = rag_tokenizer.tokenize("\n".join(req["question_kwd"]))
    if "tag_kwd" in req:
        d["tag_kwd"] = req["tag_kwd"]
    if "tag_feas" in req:
        d["tag_feas"] = req["tag_feas"]
    if "available_int" in req:
        d["available_int"] = req["available_int"]
    if "img_id" in req:
        d["img_id"] = req["img_id"]

    try:
        tenant_id = DocumentService.get_tenant_id(req["doc_id"])
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")

        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")

        # 检查是否只是更新img_id，如果是则跳过嵌入计算
        only_img_update = (
            len(req) == 4  # doc_id, chunk_id, content_with_weight, img_id
            and "img_id" in req
            and all(key in ["doc_id", "chunk_id", "content_with_weight", "img_id"] for key in req.keys())
        )

        print(f"[DEBUG] Request keys: {list(req.keys())}, only_img_update: {only_img_update}")

        if only_img_update:
            # 只更新img_id，不需要重新计算嵌入
            print(f"[DEBUG] Updating only img_id: {req['img_id']} for chunk: {req['chunk_id']}")
            update_data = {"id": req["chunk_id"], "img_id": req["img_id"]}
            settings.docStoreConn.update({"id": req["chunk_id"]}, update_data, search.index_name(tenant_id), doc.kb_id)
            return get_json_result(data=True)

        # 正常的更新流程，需要重新计算嵌入
        embd_id = DocumentService.get_embd_id(req["doc_id"])
        embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, embd_id)

        if doc.parser_id == ParserType.QA:
            arr = [t for t in re.split(r"[\n\t]", req["content_with_weight"]) if len(t) > 1]
            q, a = rmPrefix(arr[0]), rmPrefix("\n".join(arr[1:]))
            d = beAdoc(d, q, a, not any([rag_tokenizer.is_chinese(t) for t in q + a]))

        v, c = embd_mdl.encode([doc.name, req["content_with_weight"] if not d.get("question_kwd") else "\n".join(d["question_kwd"])])
        v = 0.1 * v[0] + 0.9 * v[1] if doc.parser_id != ParserType.QA else v[1]
        d["q_%d_vec" % len(v)] = v.tolist()
        settings.docStoreConn.update({"id": req["chunk_id"]}, d, search.index_name(tenant_id), doc.kb_id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/switch", methods=["POST"])  # noqa: F821
@login_required
@validate_request("chunk_ids", "available_int", "doc_id")
def switch():
    req = request.json
    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        for cid in req["chunk_ids"]:
            if not settings.docStoreConn.update({"id": cid}, {"available_int": int(req["available_int"])}, search.index_name(DocumentService.get_tenant_id(req["doc_id"])), doc.kb_id):
                return get_data_error_result(message="Index updating failure")
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/rm", methods=["POST"])  # noqa: F821
@login_required
@validate_request("chunk_ids", "doc_id")
def rm():
    from rag.utils.storage_factory import STORAGE_IMPL

    req = request.json
    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        if not settings.docStoreConn.delete({"id": req["chunk_ids"]}, search.index_name(current_user.id), doc.kb_id):
            return get_data_error_result(message="Index updating failure")
        deleted_chunk_ids = req["chunk_ids"]
        chunk_number = len(deleted_chunk_ids)
        DocumentService.decrement_chunk_num(doc.id, doc.kb_id, 1, chunk_number, 0)
        for cid in deleted_chunk_ids:
            if STORAGE_IMPL.obj_exist(doc.kb_id, cid):
                STORAGE_IMPL.rm(doc.kb_id, cid)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/create", methods=["POST"])  # noqa: F821
@login_required
@validate_request("doc_id", "content_with_weight")
def create():
    req = request.json
    chunck_id = xxhash.xxh64((req["content_with_weight"] + req["doc_id"]).encode("utf-8")).hexdigest()
    d = {"id": chunck_id, "content_ltks": rag_tokenizer.tokenize(req["content_with_weight"]), "content_with_weight": req["content_with_weight"]}
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])
    d["important_kwd"] = req.get("important_kwd", [])
    d["important_tks"] = rag_tokenizer.tokenize(" ".join(req.get("important_kwd", [])))
    d["question_kwd"] = req.get("question_kwd", [])
    d["question_tks"] = rag_tokenizer.tokenize("\n".join(req.get("question_kwd", [])))
    d["create_time"] = str(datetime.datetime.now()).replace("T", " ")[:19]
    d["create_timestamp_flt"] = datetime.datetime.now().timestamp()

    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        d["kb_id"] = [doc.kb_id]
        d["docnm_kwd"] = doc.name
        d["title_tks"] = rag_tokenizer.tokenize(doc.name)
        d["doc_id"] = doc.id

        tenant_id = DocumentService.get_tenant_id(req["doc_id"])
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")

        e, kb = KnowledgebaseService.get_by_id(doc.kb_id)
        if not e:
            return get_data_error_result(message="Knowledgebase not found!")
        if kb.pagerank:
            d[PAGERANK_FLD] = kb.pagerank

        embd_id = DocumentService.get_embd_id(req["doc_id"])
        embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING.value, embd_id)

        v, c = embd_mdl.encode([doc.name, req["content_with_weight"] if not d["question_kwd"] else "\n".join(d["question_kwd"])])
        v = 0.1 * v[0] + 0.9 * v[1]
        d["q_%d_vec" % len(v)] = v.tolist()
        settings.docStoreConn.insert([d], search.index_name(tenant_id), doc.kb_id)

        DocumentService.increment_chunk_num(doc.id, doc.kb_id, c, 1, 0)
        return get_json_result(data={"chunk_id": chunck_id})
    except Exception as e:
        return server_error_response(e)


@manager.route("/retrieval_test", methods=["POST"])  # noqa: F821
@login_required
@validate_request("kb_id", "question")
def retrieval_test():
    """
    检索测试接口，使用混合检索策略（图片向量 + 文本向量 + 关键词 + RRF融合 + Rerank）

    请求参数:
        kb_id (str | list): 知识库 ID，支持单个或多个
        question (str): 检索问题

    返回格式:
        {
            "total": int,
            "chunks": [
                {
                    "page_id": str,
                    "doc_id": str,
                    "kb_id": str,
                    "docnm_kwd": str,
                    "content_with_weight": str,
                    "page_num_int": int,
                    "img_url": str,
                    "score": float
                }
            ]
        }
    """
    req = request.json
    question = req["question"]
    kb_ids = req["kb_id"]

    # 如果kb_ids是字符串，将其转换为列表
    if isinstance(kb_ids, str):
        kb_ids = [kb_ids]

    tenant_ids = []

    try:
        # ===================
        # 第一步：查询当前用户所属的租户
        # ===================
        tenants = UserTenantService.query(user_id=current_user.id)
        if not tenants:
            return get_data_error_result(message="Tenant not found!")

        # ===================
        # 第二步：验证知识库权限，并收集租户ID
        # ===================
        for kb_id in kb_ids:
            found = False
            for tenant in tenants:
                if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
                    tenant_ids.append(tenant.tenant_id)
                    found = True
                    break
            if not found:
                return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

        # 去重租户ID
        tenant_ids = list(set(tenant_ids))

        # ===================
        # 第三步：获取知识库信息
        # ===================
        kbs = KnowledgebaseService.get_by_ids(kb_ids)
        if not kbs:
            return get_data_error_result(message="Knowledgebase not found!")

        # ===================
        # 第四步：获取并验证embedding模型（所有知识库必须使用相同的embedding模型）
        # ===================
        embedding_list = list(set([kb.embd_id for kb in kbs]))
        if len(embedding_list) != 1:
            return get_json_result(
                data=False,
                message="Knowledge bases use different embedding models.",
                code=settings.RetCode.OPERATING_ERROR
            )
        embedding_model_name = embedding_list[0]
        embd_mdl = LLMBundle(tenant_ids[0], LLMType.EMBEDDING, embedding_model_name)

        # ===================
        # 第五步：获取租户的默认模型配置（chat、rerank）
        # ===================
        tenant_infos = TenantService.get_info_by(current_user.id)
        if not tenant_infos:
            return get_data_error_result(message="Tenant info not found!")

        # 使用租户的默认chat模型
        tenant_llm_id = tenant_infos[0].get("llm_id")
        chat_mdl = LLMBundle(tenant_ids[0], LLMType.CHAT, tenant_llm_id)

        # 使用租户的默认rerank模型
        rerank_mdl = None
        tenant_rerank_id = tenant_infos[0].get("rerank_id")
        if tenant_rerank_id:
            rerank_mdl = LLMBundle(tenant_ids[0], LLMType.RERANK, tenant_rerank_id)

        # ===================
        # 第七步：执行混合检索
        # ===================
        kbinfos = settings.retrievaler.hybrid_page_retrieval(
            question=question,
            embd_mdl=embd_mdl,
            tenant_ids=tenant_ids,
            kb_ids=kb_ids,
            rerank_mdl=rerank_mdl,
            chat_mdl=chat_mdl,
            # 使用与conversation接口相同的默认参数
            image_topk=50,
            text_topk=50,
            keyword_topk=50,
            rrf_k=60,
            rrf_topk=5,
            rerank_final_topk=3,
            similarity_threshold=0.7,
            enable_context_recall=True,
            context_recall_max_pages=1
        )

        # ===================
        # 第八步：转换img_url为HTTP URL
        # ===================
        chunks = kbinfos.get("chunks", [])

        # 转换img_url为HTTP URL
        for chunk in chunks:
            if "img_url" in chunk:
                chunk["img_url"] = convert_minio_url_to_http(chunk["img_url"])

        # 重新计算total（返回所有检索结果，不过滤）
        kbinfos["total"] = len(chunks)

        return get_json_result(data=kbinfos)

    except Exception as e:
        if "not_found" in str(e):
            return get_json_result(data=False, message="No chunk found! Check the chunk status please!", code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


# 翻译相关函数已移至前端处理，这里不再需要
