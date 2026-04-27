from src.core.config import get_settings
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.llm.embedding.lite_llm_embedding import LiteLLMEmbedding

settings = get_settings()


def get_llm_completion() -> LiteLLMCompletion:
    config = settings.generative_model
    return LiteLLMCompletion(config)


def get_llm_embedding() -> LiteLLMEmbedding:
    config = settings.embedding_model
    return LiteLLMEmbedding(config)
