from .embedding_model import (
    OpenAI_APIEmbed
)
from .chat_model import (
    OpenAI_APIChat
)

from .rerank_model import (
    OpenAI_APIRerank,
)


EmbeddingModel = {
    "OpenAI-API-Compatible": OpenAI_APIEmbed,
}


ChatModel = {
    "OpenAI-API-Compatible": OpenAI_APIChat,
}

RerankModel = {
    "OpenAI-API-Compatible": OpenAI_APIRerank
}
