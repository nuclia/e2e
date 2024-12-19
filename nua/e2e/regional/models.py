ALL_LLMS = [  # Extracted from learning/libraries/learning_models/generative.py
    "chatgpt-azure-4o",
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o-mini",
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "claude-3-5-small",
    "gemini-1-5-pro",
    "gemini-1-5-pro-vision",
    "gemini-1-5-flash",
    "gemini-1-5-flash-vision",
    "mistral",
    "azure-mistral",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    # "huggingface"
]

# Model and their corresponding embedding size
ALL_ENCODERS = {  # Extracted from learning/libraries/learning_models/encoder.py
    "en-2024-04-24": 768,
    "multilingual-2024-05-06": 1024,
    "multilingual-2023-08-16": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "gecko-embeddings-multi": 768,
    # "hf_embedding",
}

LLM_WITH_JSON_OUTPUT_SUPPORT = [
    "chatgpt-azure-4-turbo",
    "chatgpt-azure-4o",
    "chatgpt-azure-4o-mini",
    "claude-3",
    "claude-3-fast",
    "claude-3-5-fast",
    "claude-3-5-small",
    "chatgpt4",
    "chatgpt4o",
    "chatgpt4o-mini",
    "gemini-1-5-pro",
    "gemini-1-5-flash",
    "azure-mistral",
]
