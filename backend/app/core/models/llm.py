"""Factories for Bedrock-backed chat/embedding models.

Every factory here does a *lazy* import of ``langchain_aws`` so that
importing this module (and anything that imports it) never requires
``boto3``/AWS credentials to be configured. This lets the app boot and the
echo chat graph run in environments with no AWS access at all -- real
model construction only happens when one of these functions is actually
called, which today is gated behind ``Settings.has_aws_credentials``.
"""

from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache
def get_chat_model() -> Any:
    """Return a ChatBedrockConverse instance for the primary (Sonnet) model.

    Used by ``agent_bedrock_node`` for full conversational responses.
    """
    from langchain_aws import ChatBedrockConverse

    settings = get_settings()
    return ChatBedrockConverse(
        model=settings.BEDROCK_CHAT_MODEL_ID,
        region_name=settings.AWS_REGION,
    )


@lru_cache
def get_fast_model() -> Any:
    """Return a ChatBedrockConverse instance for the fast (Haiku) model.

    Used for cheap/low-latency tasks: fact extraction, entity extraction,
    memory-write decisions.
    """
    from langchain_aws import ChatBedrockConverse

    settings = get_settings()
    return ChatBedrockConverse(
        model=settings.BEDROCK_FAST_MODEL_ID,
        region_name=settings.AWS_REGION,
    )


@lru_cache
def get_embeddings() -> Any:
    """Return a BedrockEmbeddings instance (Titan text embeddings v2).

    Callers must run vectors through
    ``app.memory.db.vectorstore.normalize_embedding`` before storage or
    comparison -- this factory does not normalize.
    """
    from langchain_aws import BedrockEmbeddings

    settings = get_settings()
    return BedrockEmbeddings(
        model_id=settings.BEDROCK_EMBED_MODEL_ID,
        region_name=settings.AWS_REGION,
    )
