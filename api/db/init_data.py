import logging
import base64
import json
import os
import uuid
from copy import deepcopy

from api.db import LLMType, UserTenantRole
from api.db.db_models import init_database_tables as init_web_db, LLMFactories, LLM, TenantLLM
from api.db.services import UserService
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMFactoriesService, LLMService, TenantLLMService, LLMBundle
from api.db.services.user_service import TenantService, UserTenantService
from api import settings
from api.utils.file_utils import get_project_base_directory


def encode_to_base64(input_string):
    base64_encoded = base64.b64encode(input_string.encode("utf-8"))
    return base64_encoded.decode("utf-8")


def init_superuser():
    """
    向mysql数据库表里面提前插入一些信息
    """
    # 这个数据是向user表里面添加的数据
    user_info = {
        "id": uuid.uuid1().hex,
        "nickname": "admin",
        "password": encode_to_base64("admin"),
        "email": "admin@163.com",
        "language": "Chinese",
        "color_schema": "Bright",
        "is_superuser": True,
        "is_system": True,
        "status": "1",
    }
    # 这个数据是向tenant表里面添加的数据
    tenant = {
        "id": user_info["id"],
        "name": user_info["nickname"] + "‘s Kingdom",
        "llm_id": settings.CHAT_MDL, # 如果这里行不通，就加上@试一下
        "embd_id": settings.EMBEDDING_MDL,
        "rerank_id": settings.RERANK_MDL,
        "asr_id": settings.ASR_MDL,
        "parser_ids": settings.PARSERS,
        "img2txt_id": settings.IMAGE2TEXT_MDL,
    }
    # 用户与租户的对应关系表
    usr_tenant = {
        "tenant_id": user_info["id"], 
        "user_id": user_info["id"], 
        "invited_by": user_info["id"], 
        "role": UserTenantRole.OWNER
    }
    tenant_llm = []
    for llm in LLMService.query(fid=settings.LLM_FACTORY):
        # 把已经初始化的模型，全部都添加到用户的租户里面
        if llm.model_type == LLMType.CHAT.value:
            tenant_llm.append(
                {"tenant_id": user_info["id"], "llm_factory": settings.LLM_FACTORY, "llm_name": llm.llm_name, "model_type": llm.model_type,
                 "api_key": settings.API_KEY, "api_base": settings.CHAT_BASE_URL})
        elif llm.model_type == LLMType.EMBEDDING.value:
            tenant_llm.append(
                {"tenant_id": user_info["id"], "llm_factory": settings.LLM_FACTORY, "llm_name": llm.llm_name, "model_type": llm.model_type,
                 "api_key": settings.API_KEY, "api_base": settings.EMBEDDING_BASE_URL})
        elif llm.model_type == LLMType.RERANK.value:
            tenant_llm.append(
                {"tenant_id": user_info["id"], "llm_factory": settings.LLM_FACTORY, "llm_name": llm.llm_name, "model_type": llm.model_type,
                 "api_key": settings.API_KEY, "api_base": settings.RERANK_BASE_URL})

    if not UserService.save(**user_info):
        logging.error("can't init admin.")
        return
    TenantService.insert(**tenant)
    UserTenantService.insert(**usr_tenant)
    TenantLLMService.insert_many(tenant_llm)

    # 测试一下chat模型是不是可以正常工作
    chat_mdl = LLMBundle(tenant["id"], LLMType.CHAT, tenant["llm_id"])
    msg = chat_mdl.chat(system="", history=[{"role": "user", "content": "Hello!"}], gen_conf={})
    if msg.find("ERROR: ") == 0:
        logging.error("'{}' dosen't work. {}".format(tenant["llm_id"], msg))
    
    # 测试一下embedding模型是不是可以正常工作
    embd_mdl = LLMBundle(tenant["id"], LLMType.EMBEDDING, tenant["embd_id"])
    embeddings = embd_mdl.encode(["Hello!"])
    if embeddings is None or len(embeddings) == 0:
        logging.error("'{}' dosen't work!".format(tenant["embd_id"]))

    # 测试一下rerank模型是不是可以正常工作
    rerank_mdl = LLMBundle(tenant["id"], LLMType.RERANK, tenant["rerank_id"])
    rank = rerank_mdl.similarity(
        query="Hello!",
        documents=["Hello world!", "Test document"]
    )
    if rank is None:
        logging.error("'{}' dosen't work!".format(tenant["rerank_id"]))

def init_llm_factory():
    factory_llm_infos = json.load(
        open(
            os.path.join(get_project_base_directory(), "conf", "llm_factories.json"),
            "r",
        )
    )
    for factory_llm_info in factory_llm_infos["factory_llm_infos"]:
        llm_infos = factory_llm_info.pop("llm")
        try:
            LLMFactoriesService.save(**factory_llm_info)
        except Exception:
            pass
        LLMService.filter_delete([LLM.fid == factory_llm_info["name"]])
        for llm_info in llm_infos:
            llm_info["fid"] = factory_llm_info["name"]
            try:
                LLMService.save(**llm_info)
            except Exception:
                pass



def init_web_data():
    init_llm_factory()

    # 只有user表里面没有用户时，说明启动这个项目的时候，是第一次启动，所以需要插入一下用户。
    if not UserService.get_all():
        init_superuser()



if __name__ == "__main__":
    init_web_db()
    init_web_data()
