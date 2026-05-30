import json
import os

from flask import request
from flask_login import current_user, login_required

from api import settings
from api.constants import DATASET_NAME_LIMIT
from api.db import FileSource, StatusEnum, TenantPermission
from api.db.db_models import File, Dialog, User
from api.db.services import duplicate_name
from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from api.db.services.file_service import FileService
from api.db.services.dialog_service import DialogService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService, UserTenantService
from api.db.services.user_class_service import UserClassService
from api.db.services.class_dialog_service import ClassDialogService
from api.utils import get_uuid
from api.utils.api_utils import get_data_error_result, get_json_result, not_allowed_parameters, server_error_response, validate_request
from rag.nlp import search
from rag.settings import PAGERANK_FLD


@manager.route("/create", methods=["post"])  # noqa: F821
@login_required
@validate_request("name")
def create():
    req = request.json
    dataset_name = req["name"]
    if not isinstance(dataset_name, str):
        return get_data_error_result(message="Dataset name must be string.")
    if dataset_name == "":
        return get_data_error_result(message="Dataset name can't be empty.")
    if len(dataset_name) >= DATASET_NAME_LIMIT:
        return get_data_error_result(message=f"Dataset name length is {len(dataset_name)} which is large than {DATASET_NAME_LIMIT}")

    dataset_name = dataset_name.strip()
    dataset_name = duplicate_name(KnowledgebaseService.query, name=dataset_name, tenant_id=current_user.id, status=StatusEnum.VALID.value)
    try:
        req["id"] = get_uuid()
        req["tenant_id"] = current_user.id
        req["created_by"] = current_user.id
        e, t = TenantService.get_by_id(current_user.id)
        if not e:
            return get_data_error_result(message="Tenant not found.")
        req["embd_id"] = t.embd_id
        if not KnowledgebaseService.save(**req):
            return get_data_error_result()
        return get_json_result(data={"kb_id": req["id"]})
    except Exception as e:
        return server_error_response(e)


@manager.route("/update", methods=["post"])  # noqa: F821
@login_required
@validate_request("kb_id", "name", "description", "permission", "parser_id")
@not_allowed_parameters("id", "tenant_id", "created_by", "create_time", "update_time", "create_date", "update_date", "created_by")
def update():
    req = request.json
    req["name"] = req["name"].strip()
    if not KnowledgebaseService.accessible4deletion(req["kb_id"], current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    try:
        if not KnowledgebaseService.query(created_by=current_user.id, id=req["kb_id"]):
            return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

        e, kb = KnowledgebaseService.get_by_id(req["kb_id"])
        if not e:
            return get_data_error_result(message="Can't find this knowledgebase!")

        if req.get("parser_id", "") == "tag" and os.environ.get("DOC_ENGINE", "elasticsearch") == "infinity":
            return get_json_result(data=False, message="The chunk method Tag has not been supported by Infinity yet.", code=settings.RetCode.OPERATING_ERROR)

        if req["name"].lower() != kb.name.lower() and len(KnowledgebaseService.query(name=req["name"], tenant_id=current_user.id, status=StatusEnum.VALID.value)) > 1:
            return get_data_error_result(message="Duplicated knowledgebase name.")

        del req["kb_id"]
        if not KnowledgebaseService.update_by_id(kb.id, req):
            return get_data_error_result()

        if kb.pagerank != req.get("pagerank", 0):
            if req.get("pagerank", 0) > 0:
                settings.docStoreConn.update({"kb_id": kb.id}, {PAGERANK_FLD: req["pagerank"]}, search.index_name(kb.tenant_id), kb.id)
            else:
                # Elasticsearch requires PAGERANK_FLD be non-zero!
                settings.docStoreConn.update({"exists": PAGERANK_FLD}, {"remove": PAGERANK_FLD}, search.index_name(kb.tenant_id), kb.id)

        e, kb = KnowledgebaseService.get_by_id(kb.id)
        if not e:
            return get_data_error_result(message="Database error (Knowledgebase rename)!")
        kb = kb.to_dict()
        kb.update(req)

        return get_json_result(data=kb)
    except Exception as e:
        return server_error_response(e)


@manager.route("/detail", methods=["GET"])  # noqa: F821
@login_required
def detail():
    """
    查询一个知识库里面到底有哪些文件
    """
    kb_id = request.args["kb_id"]
    try:
        # 查询当前用户都在哪些租户下面，大概率就是一个
        # 老师，可以查到两个租户，一个是system，一个是自己。
        # 学生，可以查到1个租户，就是老师。
        tenants = UserTenantService.query(user_id=current_user.id)
        # 这里主要是用于判断能不能查看
        for tenant in tenants:
            # 根据tenant_id和kb_id来查询当前对应的知识库
            if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
                break
        else:
            return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)
        
        kb = KnowledgebaseService.get_detail(kb_id)
        if not kb:
            return get_data_error_result(message="Can't find this knowledgebase!")
        return get_json_result(data=kb)
    except Exception as e:
        return server_error_response(e)


@manager.route("/list", methods=["GET"])  # noqa: F821
@login_required
def list_kbs():
    # 列出当前用户拥有哪些知识库
    # 老师(is_superuser=1)可以查看租户下所有知识库
    # 学生(is_superuser=0)只能查看自己班级下的dialog关联的知识库
    keywords = request.args.get("keywords", "")
    page_number = int(request.args.get("page", 1))
    items_per_page = int(request.args.get("page_size", 150))
    parser_id = request.args.get("parser_id")
    orderby = request.args.get("orderby", "create_time")
    desc = request.args.get("desc", True)
    try:
        if current_user.is_superuser:
            # 老师：查询租户下所有知识库（使用原有逻辑）
            tenants = TenantService.get_joined_tenants_by_user_id(current_user.id)
            print('@'*50)
            print('查询当前用户所属于的租户')
            print(tenants)
            kbs, total = KnowledgebaseService.get_by_tenant_ids(
                [m["tenant_id"] for m in tenants],
                current_user.id,
                page_number,
                items_per_page,
                orderby,
                desc,
                keywords,
                parser_id
            )
            return get_json_result(data={"kbs": kbs, "total": total})
        else:
            # 学生：只查询自己班级下的dialog关联的知识库
            # 1. 获取用户所在的班级
            user_classes = UserClassService.get_by_user(current_user.id, status=StatusEnum.VALID.value)
            if not user_classes:
                # 用户不在任何班级，返回空列表
                return get_json_result(data={"kbs": [], "total": 0})

            class_ids = [uc.class_id for uc in user_classes]

            # 2. 获取这些班级关联的dialog_id
            class_dialogs = ClassDialogService.model.select().where(
                ClassDialogService.model.class_id.in_(class_ids)
            )
            dialog_ids = [cd.dialog_id for cd in class_dialogs]

            if not dialog_ids:
                # 班级下没有dialog，返回空列表
                return get_json_result(data={"kbs": [], "total": 0})

            # 3. 获取这些dialog中的kb_ids（去重）
            dialogs = DialogService.model.select(DialogService.model.kb_ids).where(
                DialogService.model.id.in_(dialog_ids)
            )

            # 收集所有kb_ids并去重
            kb_ids_set = set()
            for dialog in dialogs:
                if dialog.kb_ids:
                    kb_ids_set.update(dialog.kb_ids)

            if not kb_ids_set:
                # dialog中没有关联知识库，返回空列表
                return get_json_result(data={"kbs": [], "total": 0})

            kb_ids = list(kb_ids_set)

            # 4. 查询这些知识库（与老师返回格式一致）
            fields = [
                KnowledgebaseService.model.id,
                KnowledgebaseService.model.avatar,
                KnowledgebaseService.model.name,
                KnowledgebaseService.model.language,
                KnowledgebaseService.model.description,
                KnowledgebaseService.model.permission,
                KnowledgebaseService.model.doc_num,
                KnowledgebaseService.model.token_num,
                KnowledgebaseService.model.chunk_num,
                KnowledgebaseService.model.parser_id,
                KnowledgebaseService.model.embd_id,
                KnowledgebaseService.model.update_time,
                User.nickname,
                User.avatar.alias('tenant_avatar')
            ]

            query = KnowledgebaseService.model.select(*fields).join(
                User, on=(KnowledgebaseService.model.tenant_id == User.id)
            ).where(
                (KnowledgebaseService.model.id.in_(kb_ids)) &
                (KnowledgebaseService.model.status == StatusEnum.VALID.value) &
                (KnowledgebaseService.model.permission == TenantPermission.TEAM.value)  # 学生只能看到team权限的知识库
            )

            # 应用过滤条件
            if keywords:
                query = query.where(KnowledgebaseService.model.name.contains(keywords))
            if parser_id:
                query = query.where(KnowledgebaseService.model.parser_id == parser_id)

            # 排序
            if desc:
                query = query.order_by(KnowledgebaseService.model.getter_by(orderby).desc())
            else:
                query = query.order_by(KnowledgebaseService.model.getter_by(orderby).asc())

            # 分页
            total = query.count()
            kbs = query.paginate(page_number, items_per_page)

            return get_json_result(data={"kbs": list(kbs.dicts()), "total": total})
    except Exception as e:
        return server_error_response(e)


@manager.route("/rm", methods=["post"])  # noqa: F821
@login_required
@validate_request("kb_id")
def rm():
    req = request.json
    if not KnowledgebaseService.accessible4deletion(req["kb_id"], current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    try:
        kbs = KnowledgebaseService.query(created_by=current_user.id, id=req["kb_id"])
        if not kbs:
            return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

        for doc in DocumentService.query(kb_id=req["kb_id"]):
            if not DocumentService.remove_document(doc, kbs[0].tenant_id):
                return get_data_error_result(message="Database error (Document removal)!")
            f2d = File2DocumentService.get_by_document_id(doc.id)
            if f2d:
                FileService.filter_delete([File.source_type == FileSource.KNOWLEDGEBASE, File.id == f2d[0].file_id])
            File2DocumentService.delete_by_document_id(doc.id)
        FileService.filter_delete([File.source_type == FileSource.KNOWLEDGEBASE, File.type == "folder", File.name == kbs[0].name])
        if not KnowledgebaseService.delete_by_id(req["kb_id"]):
            return get_data_error_result(message="Database error (Knowledgebase removal)!")
        for kb in kbs:
            settings.docStoreConn.delete({"kb_id": kb.id}, search.index_name(kb.tenant_id), kb.id)
            settings.docStoreConn.deleteIdx(search.index_name(kb.tenant_id), kb.id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/<kb_id>/tags", methods=["GET"])  # noqa: F821
@login_required
def list_tags(kb_id):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    tags = settings.retrievaler.all_tags(current_user.id, [kb_id])
    return get_json_result(data=tags)


@manager.route("/tags", methods=["GET"])  # noqa: F821
@login_required
def list_tags_from_kbs():
    kb_ids = request.args.get("kb_ids", "").split(",")
    for kb_id in kb_ids:
        if not KnowledgebaseService.accessible(kb_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    tags = settings.retrievaler.all_tags(current_user.id, kb_ids)
    return get_json_result(data=tags)


@manager.route("/<kb_id>/rm_tags", methods=["POST"])  # noqa: F821
@login_required
def rm_tags(kb_id):
    req = request.json
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    e, kb = KnowledgebaseService.get_by_id(kb_id)

    for t in req["tags"]:
        settings.docStoreConn.update({"tag_kwd": t, "kb_id": [kb_id]}, {"remove": {"tag_kwd": t}}, search.index_name(kb.tenant_id), kb_id)
    return get_json_result(data=True)


@manager.route("/<kb_id>/rename_tag", methods=["POST"])  # noqa: F821
@login_required
def rename_tags(kb_id):
    req = request.json
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    e, kb = KnowledgebaseService.get_by_id(kb_id)

    settings.docStoreConn.update(
        {"tag_kwd": req["from_tag"], "kb_id": [kb_id]}, {"remove": {"tag_kwd": req["from_tag"].strip()}, "add": {"tag_kwd": req["to_tag"]}}, search.index_name(kb.tenant_id), kb_id
    )
    return get_json_result(data=True)


@manager.route("/<kb_id>/knowledge_graph", methods=["GET"])  # noqa: F821
@login_required
def knowledge_graph(kb_id):
    # 判断当前的用户是不是属于knowledge的租户组里面的
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    # 获取到mysql中的knowledge这张表
    _, kb = KnowledgebaseService.get_by_id(kb_id)

    # 不再使用 knowledge_graph_kwd 过滤，因为索引中可能没有这个字段
    req = {"kb_id": [kb_id]}

    obj = {"graph": {}, "mind_map": {}}

    # 这里使用的存储索引是es的索引，所以第二个参数没有任何作用
    if not settings.docStoreConn.indexExist(search.index_name(kb.tenant_id), kb_id):
        return get_json_result(data=obj)

    # 使用retrieval检索器来进行检索
    sres = settings.retrievaler.search(req, search.index_name(kb.tenant_id), [kb_id])
    if not len(sres.ids):
        return get_json_result(data=obj)

    # 检查是否有知识图谱数据
    has_knowledge_graph = False
    for id in sres.ids[:1]:
        # 检查字段是否存在
        if "knowledge_graph_kwd" not in sres.field[id]:
            # 索引中没有知识图谱字段，返回空结果
            break

        ty = sres.field[id]["knowledge_graph_kwd"]
        try:
            content_json = json.loads(sres.field[id]["content_with_weight"])
        except Exception:
            continue

        obj[ty] = content_json
        has_knowledge_graph = True

    # 如果没有知识图谱数据，直接返回空结果
    if not has_knowledge_graph:
        return get_json_result(data=obj)

    if "nodes" in obj["graph"]:
        obj["graph"]["nodes"] = sorted(obj["graph"]["nodes"], key=lambda x: x.get("pagerank", 0), reverse=True)[:256]
        if "edges" in obj["graph"]:
            node_id_set = {o["id"] for o in obj["graph"]["nodes"]}
            filtered_edges = [o for o in obj["graph"]["edges"] if o["source"] != o["target"] and o["source"] in node_id_set and o["target"] in node_id_set]
            obj["graph"]["edges"] = sorted(filtered_edges, key=lambda x: x.get("weight", 0), reverse=True)[:128]
    return get_json_result(data=obj)


@manager.route("/images", methods=["GET"])  # noqa: F821
@login_required
def get_kb_images():
    kb_id = request.args.get("kb_id")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    search_text = request.args.get("search", "")

    if not kb_id:
        return get_json_result(data=False, message="Knowledge base ID is required.", code=settings.RetCode.ARGUMENT_ERROR)

    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    try:
        _, kb = KnowledgebaseService.get_by_id(kb_id)

        # 获取知识库下的所有文档
        from api.db.services.document_service import DocumentService

        docs = DocumentService.get_by_kb_id(kb_id, 1, 10000, "create_time", False, "")  # 获取所有文档

        all_images = []

        # 遍历每个文档，获取其chunks
        for doc in docs[0]:  # docs返回(documents, total)
            try:
                # 使用chunk_list方法获取文档的所有chunks
                chunks = settings.retrievaler.chunk_list(doc_id=doc["id"], tenant_id=kb.tenant_id, kb_ids=[kb_id], fields=["docnm_kwd", "content_with_weight", "img_id", "doc_id"])

                # 筛选有图片的chunks
                for chunk in chunks:
                    if chunk.get("img_id") and chunk["img_id"].strip():
                        # 如果有搜索条件，进行内容过滤
                        if search_text and search_text.lower() not in chunk.get("content_with_weight", "").lower():
                            continue

                        print(f"Found chunk with image: {chunk['id']}, img_id: {chunk['img_id']}")  # 调试信息

                        all_images.append(
                            {
                                "img_id": chunk["img_id"],
                                "doc_id": chunk["doc_id"],
                                "doc_name": chunk["docnm_kwd"],
                                "chunk_id": chunk["id"],
                                "content": chunk["content_with_weight"][:200] + "..." if len(chunk["content_with_weight"]) > 200 else chunk["content_with_weight"],
                            }
                        )
            except Exception as e:
                print(f"Error processing document {doc['id']}: {e}")
                continue

        # 分页处理
        total_images = len(all_images)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_images = all_images[start_idx:end_idx]

        result = {"images": paginated_images, "total": total_images, "page": page, "page_size": page_size}

        print(f"Total images found: {total_images}")
        print(f"Returning {len(paginated_images)} images for page {page}")

        result = {"images": paginated_images, "total": total_images, "page": page, "page_size": page_size}
        print(f"API result: {result}")

        return get_json_result(data=result)

    except Exception as e:
        return server_error_response(e)
