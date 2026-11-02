#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
from datetime import date
from enum import IntEnum, Enum
import rag.utils.es_conn
import rag.utils.infinity_conn

import rag.utils
from rag.nlp import search
from api.utils import get_base_config, decrypt_database_config
from api.constants import RAG_FLOW_SERVICE_NAME

LIGHTEN = int(os.environ.get("LIGHTEN", "0"))

LLM = None # service_conf里面配置的user_default_llm
LLM_FACTORY = None # 模型厂商
LLM_BASE_URL = None # 模型的url
CHAT_MDL = "" # 聊天模型
CHAT_BASE_URL = "" # 聊天模型的地址
EMBEDDING_MDL = "" # 嵌入模型
EMBEDDING_BASE_URL = "" # 嵌入模型的地址
RERANK_MDL = "" # rerank模型
RERANK_BASE_URL = "" # rerank模型的地址
ASR_MDL = "" # 语音转文字模型
IMAGE2TEXT_MDL = "" # 图像转文字模型
API_KEY = None # api_key
PARSERS = None
HOST_IP = None
HOST_PORT = None
SECRET_KEY = None

DATABASE_TYPE = os.getenv("DB_TYPE", "mysql")
DATABASE = decrypt_database_config(name=DATABASE_TYPE)

# authentication
AUTHENTICATION_CONF = None

# client
CLIENT_AUTHENTICATION = None
HTTP_APP_KEY = None
GITHUB_OAUTH = None
FEISHU_OAUTH = None

DOC_ENGINE = None
docStoreConn = None

retrievaler = None


def init_settings():
    global LLM, LLM_FACTORY, LLM_BASE_URL, LIGHTEN, DATABASE_TYPE, DATABASE, CHAT_BASE_URL, EMBEDDING_BASE_URL,RERANK_BASE_URL, CHAT_MDL, EMBEDDING_MDL, RERANK_MDL, ASR_MDL, IMAGE2TEXT_MDL
    LIGHTEN = int(os.environ.get("LIGHTEN", "0"))
    DATABASE_TYPE = os.getenv("DB_TYPE", "mysql")
    DATABASE = decrypt_database_config(name=DATABASE_TYPE)

    # 在这里获取到模service_conf里面配置的东西
    LLM = get_base_config("user_default_llm", {})
    LLM_DEFAULT_MODELS = LLM.get("default_models", {})
    LLM_FACTORY = LLM.get("factory", "OpenAI-API-Compatible")

    # chat和embedding的地址
    CHAT_BASE_URL = LLM.get("chat_base_url")
    EMBEDDING_BASE_URL = LLM.get("embedding_base_url")
    RERANK_BASE_URL = LLM.get('rerank_base_url')

    # chat和embedding的名称
    CHAT_MDL = LLM.get("chat_model", "")
    EMBEDDING_MDL = LLM.get("embedding_model", "")
    RERANK_MDL = LLM.get("rerank_model", "")


    LLM_BASE_URL = LLM.get("base_url")

    if LLM_DEFAULT_MODELS:
        CHAT_MDL = LLM_DEFAULT_MODELS.get("chat_model", CHAT_MDL)
        EMBEDDING_MDL = LLM_DEFAULT_MODELS.get("embedding_model", EMBEDDING_MDL)
        RERANK_MDL = LLM_DEFAULT_MODELS.get("rerank_model", RERANK_MDL)
        ASR_MDL = LLM_DEFAULT_MODELS.get("asr_model", ASR_MDL)
        IMAGE2TEXT_MDL = LLM_DEFAULT_MODELS.get("image2text_model", IMAGE2TEXT_MDL)

        # factory can be specified in the config name with "@". LLM_FACTORY will be used if not specified
        CHAT_MDL = CHAT_MDL + (f"@{LLM_FACTORY}" if "@" not in CHAT_MDL and CHAT_MDL != "" else "")
        EMBEDDING_MDL = EMBEDDING_MDL + (f"@{LLM_FACTORY}" if "@" not in EMBEDDING_MDL and EMBEDDING_MDL != "" else "")
        RERANK_MDL = RERANK_MDL + (f"@{LLM_FACTORY}" if "@" not in RERANK_MDL and RERANK_MDL != "" else "")
        ASR_MDL = ASR_MDL + (f"@{LLM_FACTORY}" if "@" not in ASR_MDL and ASR_MDL != "" else "")
        IMAGE2TEXT_MDL = IMAGE2TEXT_MDL + (f"@{LLM_FACTORY}" if "@" not in IMAGE2TEXT_MDL and IMAGE2TEXT_MDL != "" else "")

    global API_KEY, PARSERS, HOST_IP, HOST_PORT, SECRET_KEY
    API_KEY = LLM.get("api_key", "")
    PARSERS = LLM.get("parsers","naive:General,qa:Q&A,resume:Resume,manual:Manual,table:Table,paper:Paper,book:Book,laws:Laws,presentation:Presentation,picture:Picture,one:One,audio:Audio,knowledge_graph:Knowledge Graph,email:Email,tag:Tag")
    HOST_IP = get_base_config(RAG_FLOW_SERVICE_NAME, {}).get("host", "127.0.0.1")
    HOST_PORT = get_base_config(RAG_FLOW_SERVICE_NAME, {}).get("http_port")

    # 优先使用部署环境提供的固定密钥，其次使用 service_conf.yaml 中的配置。
    # 不能把当前日期作为长期运行服务的密钥，否则跨天或重启后已有 Token 会失效。
    ragflow_config = get_base_config(RAG_FLOW_SERVICE_NAME, {})
    SECRET_KEY = (
        os.environ.get("RAGFLOW_SECRET_KEY")
        or ragflow_config.get("secret_key")
        or str(date.today())
    )

    global AUTHENTICATION_CONF, CLIENT_AUTHENTICATION, HTTP_APP_KEY, GITHUB_OAUTH, FEISHU_OAUTH
    # authentication
    AUTHENTICATION_CONF = get_base_config("authentication", {})

    # client
    CLIENT_AUTHENTICATION = AUTHENTICATION_CONF.get("client", {}).get("switch", False)
    HTTP_APP_KEY = AUTHENTICATION_CONF.get("client", {}).get("http_app_key")
    GITHUB_OAUTH = get_base_config("oauth", {}).get("github")
    FEISHU_OAUTH = get_base_config("oauth", {}).get("feishu")

    global DOC_ENGINE, docStoreConn, retrievaler
    DOC_ENGINE = os.environ.get("DOC_ENGINE", "elasticsearch")
    lower_case_doc_engine = DOC_ENGINE.lower()
    if lower_case_doc_engine == "elasticsearch":
        # 默认情况下用的就是es的检索引擎
        # 这里也是初始化了一个文档存储的连接对象？
        docStoreConn = rag.utils.es_conn.ESConnection()
    elif lower_case_doc_engine == "infinity":
        docStoreConn = rag.utils.infinity_conn.InfinityConnection()
    else:
        raise Exception(f"Not supported doc engine: {DOC_ENGINE}")

    # 核心就是这个检索器
    # 这个初始化了一个检索器对象
    retrievaler = search.Dealer(docStoreConn)


class CustomEnum(Enum):
    @classmethod
    def valid(cls, value):
        try:
            cls(value)
            return True
        except BaseException:
            return False

    @classmethod
    def values(cls):
        return [member.value for member in cls.__members__.values()]

    @classmethod
    def names(cls):
        return [member.name for member in cls.__members__.values()]


class RetCode(IntEnum, CustomEnum):
    SUCCESS = 0
    NOT_EFFECTIVE = 10
    EXCEPTION_ERROR = 100
    ARGUMENT_ERROR = 101
    DATA_ERROR = 102
    OPERATING_ERROR = 103
    CONNECTION_ERROR = 105
    RUNNING = 106
    PERMISSION_ERROR = 108
    AUTHENTICATION_ERROR = 109
    UNAUTHORIZED = 401
    SERVER_ERROR = 500
    FORBIDDEN = 403
    NOT_FOUND = 404
