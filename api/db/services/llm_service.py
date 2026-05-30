import json
import logging
import os
import numpy as np
from api.db.services.user_service import TenantService
from api.utils.file_utils import get_project_base_directory
from rag.llm import EmbeddingModel, ChatModel, RerankModel
from api.db import LLMType
from api.db.db_models import DB
from api.db.db_models import LLMFactories, LLM, TenantLLM
from api.db.services.common_service import CommonService


class LLMFactoriesService(CommonService):
    model = LLMFactories


class LLMService(CommonService):
    model = LLM


class TenantLLMService(CommonService):
    model = TenantLLM

    @classmethod
    @DB.connection_context()
    def get_api_key(cls, tenant_id, model_name):
        mdlnm, fid = TenantLLMService.split_model_name_and_factory(model_name)
        if not fid:
            objs = cls.query(tenant_id=tenant_id, llm_name=mdlnm)
        else:
            objs = cls.query(tenant_id=tenant_id, llm_name=mdlnm, llm_factory=fid)
        if not objs:
            return
        return objs[0]

    @classmethod
    @DB.connection_context()
    def get_my_llms(cls, tenant_id):
        fields = [cls.model.llm_factory, LLMFactories.logo, LLMFactories.tags, cls.model.model_type, cls.model.llm_name, cls.model.used_tokens]
        objs = cls.model.select(*fields).join(LLMFactories, on=(cls.model.llm_factory == LLMFactories.name)).where(cls.model.tenant_id == tenant_id, ~cls.model.api_key.is_null()).dicts()

        return list(objs)

    @staticmethod
    def split_model_name_and_factory(model_name):
        arr = model_name.split("@")
        if len(arr) < 2:
            return model_name, None
        if len(arr) > 2:
            return "@".join(arr[0:-1]), arr[-1]

        # model name must be xxx@yyy
        try:
            model_factories = json.load(open(os.path.join(get_project_base_directory(), "conf/llm_factories.json"), "r"))["factory_llm_infos"]
            model_providers = set([f["name"] for f in model_factories])
            if arr[-1] not in model_providers:
                return model_name, None
            return arr[0], arr[-1]
        except Exception as e:
            logging.exception(f"TenantLLMService.split_model_name_and_factory got exception: {e}")
        return model_name, None

    @classmethod
    @DB.connection_context()
    def get_model_config(cls, tenant_id, llm_type, llm_name=None):
        e, tenant = TenantService.get_by_id(tenant_id)
        if not e:
            raise LookupError("Tenant not found")

        if llm_type == LLMType.EMBEDDING.value:
            mdlnm = tenant.embd_id if not llm_name else llm_name
        elif llm_type == LLMType.CHAT.value:
            mdlnm = tenant.llm_id if not llm_name else llm_name
        elif llm_type == LLMType.RERANK:
            mdlnm = tenant.rerank_id if not llm_name else llm_name
        else:
            assert False, "LLM type error"

        # 从tenant-llm表里面来获取到模型的配置，这个model-config主要包含apikey、baseurl等信息
        model_config = cls.get_api_key(tenant_id, mdlnm)
        if model_config:
            model_config = model_config.to_dict()
        else:
            raise LookupError("not model_config")
        return model_config

    @classmethod
    @DB.connection_context()
    def model_instance(cls, tenant_id, llm_type, llm_name=None, lang="Chinese"):
        model_config = TenantLLMService.get_model_config(tenant_id, llm_type, llm_name)
        if llm_type == LLMType.EMBEDDING.value:
            if model_config["llm_factory"] not in EmbeddingModel:
                return
            return EmbeddingModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"])

        if llm_type == LLMType.RERANK:
            if model_config["llm_factory"] not in RerankModel:
                return
            return RerankModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"])


        if llm_type == LLMType.CHAT.value:
            if model_config["llm_factory"] not in ChatModel:
                return
            return ChatModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"])


    @classmethod
    @DB.connection_context()
    def increase_usage(cls, tenant_id, llm_type, used_tokens, llm_name=None):
        e, tenant = TenantService.get_by_id(tenant_id)
        if not e:
            logging.error(f"Tenant not found: {tenant_id}")
            return 0

        llm_map = {
            LLMType.EMBEDDING.value: tenant.embd_id,
            LLMType.SPEECH2TEXT.value: tenant.asr_id,
            LLMType.IMAGE2TEXT.value: tenant.img2txt_id,
            LLMType.CHAT.value: tenant.llm_id if not llm_name else llm_name,
            LLMType.RERANK.value: tenant.rerank_id if not llm_name else llm_name,
            LLMType.TTS.value: tenant.tts_id if not llm_name else llm_name,
        }

        mdlnm = llm_map.get(llm_type)
        if mdlnm is None:
            logging.error(f"LLM type error: {llm_type}")
            return 0

        llm_name, llm_factory = TenantLLMService.split_model_name_and_factory(mdlnm)

        try:
            num = (
                cls.model.update(used_tokens=cls.model.used_tokens + used_tokens)
                .where(cls.model.tenant_id == tenant_id, cls.model.llm_name == llm_name, cls.model.llm_factory == llm_factory if llm_factory else True)
                .execute()
            )
        except Exception:
            logging.exception("TenantLLMService.increase_usage got exception,Failed to update used_tokens for tenant_id=%s, llm_name=%s", tenant_id, llm_name)
            return 0

        return num

    @classmethod
    @DB.connection_context()
    def get_openai_models(cls):
        objs = cls.model.select().where((cls.model.llm_factory == "OpenAI"), ~(cls.model.llm_name == "text-embedding-3-small"), ~(cls.model.llm_name == "text-embedding-3-large")).dicts()
        return list(objs)


class LLMBundle:
    def __init__(self, tenant_id, llm_type, llm_name=None, lang="Chinese"):
        self.tenant_id = tenant_id
        self.llm_type = llm_type
        self.llm_name = llm_name
        self.mdl = TenantLLMService.model_instance(tenant_id, llm_type, llm_name, lang=lang)
        assert self.mdl, "Can't find model for {}/{}/{}".format(tenant_id, llm_type, llm_name)

    def encode(self, texts: list) -> np.ndarray:
        """
        传入一堆list，返回编码的结果
        """
        embeddings = self.mdl.encode(texts)
        return embeddings

    def encode_queries(self, query: str) -> np.ndarray:
        """
        传入单个query，来计算相似度
        """
        emd = self.mdl.encode_queries(query)
        return emd

    def similarity(self, query: str, documents: list):
        """
        TODO:这个应该是rerank模型里面需要实现的方法，计算一个query和一堆文本之间的相似度得分
        后续实现,把qwen3-vl-rerank-2b给集成进来
        """
        sim = self.mdl.similarity(query, documents)
        return sim


    def chat(self, system, history, gen_conf=None):
        txt = self.mdl.chat(system, history, gen_conf)
        return txt

    def chat_streamly(self, system, history, gen_conf=None):
        for txt in self.mdl.chat_streamly(system, history, gen_conf):
            yield txt

    def chat_with_tools(
        self,
        system: str,
        history: list,
        gen_conf: dict = None
    ):
        """支持 function calling 的对话方法"""

        return self.mdl.chat_with_tools(system, history, gen_conf)
