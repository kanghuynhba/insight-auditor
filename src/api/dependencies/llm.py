from src.domain.config import get_settings
from src.llm._completion import LiteLLMCompletion
from src.llm._embedding import LiteLLMEmbedding

settings = get_settings()


def get_llm_completion() -> LiteLLMCompletion:
    config = settings.generative_model
    return LiteLLMCompletion(config)


def get_llm_embedding() -> LiteLLMEmbedding:
    config = settings.embedding_model
    return LiteLLMEmbedding(config)
