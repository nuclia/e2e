# Extracted from
#  https://github.com/nuclia/learning/blob/main/libraries/learning_models/src/learning_models/generative.py
# specifically from `DefaultGenerativeModels``
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful
# Also delete only the model if it has been deleted on the original
import re

ALL_LLMS = [
    # "generative-multilingual-2023",        EXCLUDED because it's a legacy model, not available anymore
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "chatgpt-azure-4o-mini",
    "chatgpt-azure-o1-preview",
    # "chatgpt-azure-o1-mini",               DISCONTINUED
    # "chatgpt-azure-o1",                    EXCLUDED because it almost always fails with timeouts
    "chatgpt-azure-o3-mini",
    "claude-3",
    # "claude-3-fast",                       DISCONTINUED
    "claude-3-5-fast",
    "claude-3-5-small",
    "claude-4-opus",
    "claude-4-sonnet",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1-5-pro",
    # "gemini-1-5-pro-vision",               EXCLUDED because it shares same implementation as non-vision
    "gemini-1-5-flash",
    # "gemini-1-5-flash-vision",             EXCLUDED because it shares same implementation as non-vision
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "mistral",
    # "azure-mistral",                       DISCONTINUED
    "chatgpt4o",
    "chatgpt4o-mini",
    # "chatgpt-o1-preview",                  DISCONTINUED
    # "chatgpt-o1-mini",                     DISCONTINUED
    "chatgpt-o1",
    "chatgpt-o3-mini",
    "chatgpt-4.1",
    # "huggingface"                          EXCLUDED as not a model,just a driver, that needs a key to work
    "llama-3.2-90b-vision-instruct-maas",
    "llama-4-maverick-17b-128e-instruct-maas",
    "llama-4-scout-17b-16e-instruct-maas",
    # "deepseek-reasoner",                   DISCONTINUED
    # "deepseek-chat",                       DISCONTINUED
    # "azure-deepseek-r1",                   EXCLUDED as it is too slow
    "azure-mistral-large-2",
    "gcp-claude-3-5-sonnet-v2",
    "gcp-claude-3-7-sonnet",
    # "openai-compatible",                   EXCLUDED as not a model,just a driver, that needs a key to work
    # "deepseek-chat-openai-compat"           EXCLUDED as not a model,just a driver, that needs a key to work
]


def is_reasoning_model(model: str) -> bool:
    match = re.search(r"chatgpt.*?o\d+", model) or re.search(r"reasoner", model)
    return match is not None


NON_REASONING_LLMS = [model for model in ALL_LLMS if not is_reasoning_model(model)]

# Extracted from
#  https://github.com/nuclia/learning/blob/main/libraries/learning_models/src/learning_models/encoder.py
# specifically from `SemanticModel`
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful
# Also delete only the model if it has been deleted on the original
ALL_ENCODERS = {
    "en-2024-04-24": 768,
    "multilingual-2024-05-06": 1024,
    "multilingual-2023-08-16": 1024,
    "multilingual-2024-10-07": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "gecko-embeddings-multi": 768,
    # "hf_embedding": 768,                             Excluded because it need a key to work
}

# copy of ALL_LLMS excluding some more
LLM_WITH_JSON_OUTPUT_SUPPORT = [
    # "generative-multilingual-2023",
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "chatgpt-azure-4o-mini",
    # "chatgpt-azure-o1-preview",
    # "chatgpt-azure-o1-mini",
    # "chatgpt-azure-o1",                    EXCLUDED because it almost always fails with timeouts
    "chatgpt-azure-o3-mini",
    "claude-3",
    # "claude-3-fast",                       DISCONTINUED
    "claude-3-5-fast",
    "claude-3-5-small",
    "claude-4-opus",
    "claude-4-sonnet",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1-5-pro",
    # "gemini-1-5-pro-vision",
    "gemini-1-5-flash",
    # "gemini-1-5-flash-vision",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    # "mistral",
    # "azure-mistral",
    "chatgpt4o",
    "chatgpt4o-mini",
    # "chatgpt-o1-preview",                                DISCONTINUED
    # "chatgpt-o1-mini",                                   DISCONTINUED
    # "chatgpt-o1",
    "chatgpt-o3-mini",
    "chatgpt-4.1",
    # "huggingface"
    # "llama-3.2-90b-vision-instruct-maas",               EXCLUDED because they are pretty lame at JSON
    # "llama-4-maverick-17b-128e-instruct-maas",          EXCLUDED because they are pretty lame at JSON
    # "llama-4-scout-17b-16e-instruct-maas",              EXCLUDED because they are pretty lame at JSON
    # "deepseek-reasoner",                                DISCONTINUED
    # "deepseek-chat",                                    DISCONTINUED
    # "azure-deepseek-r1",
    "azure-mistral-large-2",
    "gcp-claude-3-5-sonnet-v2",
    "gcp-claude-3-7-sonnet",
    # "openai-compatible",
    # "deepseek-chat-openai-compat"
]
