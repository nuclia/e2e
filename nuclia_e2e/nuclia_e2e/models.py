# Extracted from
##  https://github.com/nuclia/learning/blob/main/libraries/learning_models/learning_models/generative.py
# specifically from `DefaultGenerativeModels``
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful

ALL_LLMS = [  # Extracted from learning/libraries/learning_models/generative.py
    # "generative-multilingual-2023",        WHY EXCLUDED ?
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "chatgpt-azure-4o-mini",
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "claude-3-5-small",
    # "gemini-2.0-flash-thinking-exp-1219",  WHY EXCLUDED ?
    # "gemini-2.0-flash-exp",                WHY EXCLUDED ?
    "gemini-1-5-pro",
    "gemini-1-5-pro-vision",
    "gemini-1-5-flash",
    "gemini-1-5-flash-vision",
    "mistral",
    "azure-mistral",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    "chatgpt-o1-preview",
    "chatgpt-o1-mini",
    # "llama-3.2-90b-vision-instruct-maas"   WHY EXCLUDED ?
    # "huggingface"  excluded because it need a key
]


# Extracted from
##  https://github.com/nuclia/learning/blob/main/libraries/learning_models/learning_models/encoder.py
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
    # "hf_embedding": 768,
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
