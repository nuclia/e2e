# Extracted from
#  https://github.com/nuclia/learning/blob/main/libraries/learning_models/learning_models/generative.py
# specifically from `DefaultGenerativeModels``
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful
import re


ALL_LLMS = [
    # "generative-multilingual-2023",        EXCLUDED because it's a legacy model, cannot be selected anywhere currently
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "chatgpt-azure-4o-mini",
    "chatgpt-azure-o1-preview",
    "chatgpt-azure-o1-mini",
    "chatgpt-azure-o1",
    "chatgpt-azure-o3-mini",
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "claude-3-5-small",
    # "gemini-2.0-flash-thinking-exp-1219",  EXCLUDED because they are not currently available in production
    # "gemini-2.0-flash-exp",                EXCLUDED because they are not currently available in production
    # "gemini-2.0-flash-exp",                EXCLUDED because they are not currently available in production
    # "gemini-2.0-flash-lite",               EXCLUDED because they are not currently available in production
    "gemini-2.0-flash",
    "gemini-1-5-pro",
    # "gemini-1-5-pro-vision",               EXCLUDED because it shares same implementation as non-vision
    "gemini-1-5-flash",
    # "gemini-1-5-flash-vision",             EXCLUDED because it shares same implementation as non-vision
    "mistral",
    "azure-mistral",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    "chatgpt-o1-preview",
    "chatgpt-o1-mini",
    "chatgpt-o1",
    "chatgpt-o3-mini",
    # "huggingface"                          EXCLUDED because it's not a real model, just a driver, that needs a key to work
    # "llama-3.2-90b-vision-instruct-maas"   EXCLUDED as it stopped working and was never solved
    # "deepseek-reasoner",                   EXCLUDED as it is too slow and messing all the e2e runs
    "deepseek-chat",
]


def is_reasoning_model(model: str) -> bool:
    return re.search(r"chatgpt.*?o\d+", model) or re.search(r"reasoner", model)


NON_REASONING_LLMS = [model for model in ALL_LLMS if not is_reasoning_model(model)]

# Extracted from
#  https://github.com/nuclia/learning/blob/main/libraries/learning_models/learning_models/encoder.py
# specifically from `SemanticModel`
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful
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
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "claude-3-5-small",
    # "gemini-2.0-flash-thinking-exp-1219",
    # "gemini-2.0-flash-exp",
    "gemini-1-5-pro",
    "gemini-1-5-pro-vision",
    "gemini-1-5-flash",
    "gemini-1-5-flash-vision",
    # "mistral",
    "azure-mistral",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    # "chatgpt-o1-preview",                                WHY EXCLUDED ?
    # "chatgpt-o1-mini",                                   WHY EXCLUDED ?
    # "llama-3.2-90b-vision-instruct-maas"
    # "huggingface"  # excluded because it need a key
]
