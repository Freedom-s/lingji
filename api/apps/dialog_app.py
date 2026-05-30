from flask import request
from flask_login import login_required, current_user
from api.db.services.dialog_service import DialogService
from api.db import StatusEnum
from api.db.services.llm_service import TenantLLMService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService, UserTenantService
from api.db.services.user_class_service import UserClassService
from api.db.services.class_dialog_service import ClassDialogService
from api import settings
from api.utils.api_utils import server_error_response, get_data_error_result, validate_request
from api.utils import get_uuid
from api.utils.api_utils import get_json_result


@manager.route("/set", methods=["POST"])  # noqa: F821
@login_required
def set_dialog():
    req = request.json
    dialog_id = req.get("dialog_id")
    name = req.get("name", "New Dialog")
    description = req.get("description", "一个智慧小帮手")
    icon = req.get("icon", "")
    top_n = req.get("top_n", 6)
    top_k = req.get("top_k", 1024)
    rerank_id = req.get("rerank_id", "")
    if not rerank_id:
        req["rerank_id"] = ""
    similarity_threshold = req.get("similarity_threshold", 0.1)
    vector_similarity_weight = req.get("vector_similarity_weight", 0.3)
    llm_setting = req.get("llm_setting", {})
    default_prompt = {
        "system": """你是一个智能助手，请总结知识库的内容来回答问题，请列举知识库中的数据详细回答。当所有知识库内容都与问题无关时，你的回答必须包括“知识库中未找到您要的答案！”这句话。回答需要考虑聊天历史。
以下是知识库：
{knowledge}
以上是知识库。""",
        "prologue": "您好，我是您的助手小樱，长得可爱又善良，can I help you?",
        "parameters": [{"key": "knowledge", "optional": False}],
        "empty_response": "Sorry! 知识库中未找到相关内容！",
        "use_page_retrieval": False,  # 默认使用chunk检索，可设置为True启用页面检索
    }
    prompt_config = req.get("prompt_config", default_prompt)
    
    # 确保 use_page_retrieval 字段存在（向后兼容）
    if "use_page_retrieval" not in prompt_config:
        prompt_config["use_page_retrieval"] = False

    if not prompt_config["system"]:
        prompt_config["system"] = default_prompt["system"]

    for p in prompt_config["parameters"]:
        if p["optional"]:
            continue
        if prompt_config["system"].find("{%s}" % p["key"]) < 0:
            return get_data_error_result(message="Parameter '{}' is not used".format(p["key"]))

    try:
        e, tenant = TenantService.get_by_id(current_user.id)
        if not e:
            return get_data_error_result(message="Tenant not found!")
        kbs = KnowledgebaseService.get_by_ids(req.get("kb_ids", []))
        embd_ids = [TenantLLMService.split_model_name_and_factory(kb.embd_id)[0] for kb in kbs]  # remove vendor suffix for comparison
        embd_count = len(set(embd_ids))
        if embd_count > 1:
            return get_data_error_result(message=f'Datasets use different embedding models: {[kb.embd_id for kb in kbs]}"')

        llm_id = req.get("llm_id", tenant.llm_id)
        if not dialog_id:
            dia = {
                "id": get_uuid(),
                "tenant_id": current_user.id,
                "name": name,
                "kb_ids": req.get("kb_ids", []),
                "description": description,
                "llm_id": llm_id,
                "llm_setting": llm_setting,
                "prompt_config": prompt_config,
                "top_n": top_n,
                "top_k": top_k,
                "rerank_id": rerank_id,
                "similarity_threshold": similarity_threshold,
                "vector_similarity_weight": vector_similarity_weight,
                "icon": icon,
            }
            if not DialogService.save(**dia):
                return get_data_error_result(message="Fail to new a dialog!")
            return get_json_result(data=dia)
        else:
            del req["dialog_id"]
            if "kb_names" in req:
                del req["kb_names"]
            if not DialogService.update_by_id(dialog_id, req):
                return get_data_error_result(message="Dialog not found!")
            e, dia = DialogService.get_by_id(dialog_id)
            if not e:
                return get_data_error_result(message="Fail to update a dialog!")
            dia = dia.to_dict()
            dia.update(req)
            dia["kb_ids"], dia["kb_names"] = get_kb_names(dia["kb_ids"])
            return get_json_result(data=dia)
    except Exception as e:
        return server_error_response(e)


@manager.route("/get", methods=["GET"])  # noqa: F821
@login_required
def get():
    dialog_id = request.args["dialog_id"]
    try:
        e, dia = DialogService.get_by_id(dialog_id)
        if not e:
            return get_data_error_result(message="Dialog not found!")
        dia = dia.to_dict()
        dia["kb_ids"], dia["kb_names"] = get_kb_names(dia["kb_ids"])
        return get_json_result(data=dia)
    except Exception as e:
        return server_error_response(e)


def get_kb_names(kb_ids):
    ids, nms = [], []
    for kid in kb_ids:
        e, kb = KnowledgebaseService.get_by_id(kid)
        if not e or kb.status != StatusEnum.VALID.value:
            continue
        ids.append(kid)
        nms.append(kb.name)
    return ids, nms


@manager.route("/list", methods=["GET"])  # noqa: F821
@login_required
def list_dialogs():
    try:
        # 老师(is_superuser=1)可以查看租户下所有dialog
        # 学生(is_superuser=0)只能查看自己班级下的dialog
        if current_user.is_superuser:
            # 老师：查询租户下所有dialog
            diags = DialogService.query(
                tenant_id=current_user.id,
                status=StatusEnum.VALID.value,
                reverse=True,
                order_by=DialogService.model.create_time
            )
        else:
            # 学生：只查询自己班级下的dialog
            # 1. 获取用户所在的班级
            user_classes = UserClassService.get_by_user(current_user.id, status=StatusEnum.VALID.value)
            if not user_classes:
                # 用户不在任何班级，返回空列表
                return get_json_result(data=[])

            # 查到当前用户的所有所在班级
            class_ids = [uc.class_id for uc in user_classes]
            print('@'*50)
            print(class_ids)
            # 2. 获取这些班级关联的dialog_id
            class_dialogs = ClassDialogService.model.select().where(
                ClassDialogService.model.class_id.in_(class_ids) # 查到这些班级都配置了哪些知识库
            )
            dialog_ids = [cd.dialog_id for cd in class_dialogs]

            if not dialog_ids:
                # 班级下没有dialog，返回空列表
                return get_json_result(data=[])

            # 3. 只返回这些dialog
            diags = DialogService.model.select().where(
                (DialogService.model.id.in_(dialog_ids)) &
                (DialogService.model.status == StatusEnum.VALID.value)
            ).order_by(DialogService.model.create_time.desc())

        diags = [d.to_dict() for d in diags]
        for d in diags:
            d["kb_ids"], d["kb_names"] = get_kb_names(d["kb_ids"])
        return get_json_result(data=diags)
    except Exception as e:
        return server_error_response(e)


@manager.route("/rm", methods=["POST"])  # noqa: F821
@login_required
@validate_request("dialog_ids")
def rm():
    req = request.json
    dialog_list = []
    tenants = UserTenantService.query(user_id=current_user.id)
    try:
        for id in req["dialog_ids"]:
            for tenant in tenants:
                if DialogService.query(tenant_id=tenant.tenant_id, id=id):
                    break
            else:
                return get_json_result(data=False, message="Only owner of dialog authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)
            dialog_list.append({"id": id, "status": StatusEnum.INVALID.value})
        DialogService.update_many_by_id(dialog_list)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
