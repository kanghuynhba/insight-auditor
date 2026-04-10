import os
import time

from lancedb.embeddings import EmbeddingFunctionRegistry, get_registry
from src.core.config import get_settings

settings = get_settings()

# Set the var first
registry = EmbeddingFunctionRegistry.get_instance()
registry.set_var(
    "AZURE_OPENAI_API_KEY", settings.azure_openai_api_key.get_secret_value()
)

raw_url = str(settings.azure_openai_endpoint)
clean_endpoint = raw_url.split("/openai/")[0].rstrip("/")

print("Calling registry.create()...")
start = time.time()

embed_func = (
    get_registry()
    .get("openai")
    .create(
        name=str(settings.embedding_model),
        api_key="$var:AZURE_OPENAI_API_KEY",
        azure_endpoint=clean_endpoint,
        use_azure=True,
        api_version=str(settings.openai_api_version),
        dim=1536,
        timeout=15,
    )
)

print(f"registry.create() done in {time.time()-start:.2f}s")

# Now test actually calling it
print("Calling embed_func directly...")
start = time.time()
result = embed_func.compute_query_embeddings("hello world")
print(f"embed_func call done in {time.time()-start:.2f}s — dim={len(result[0])}")
