# Extracted from
#  https://github.com/nuclia/learning/blob/main/libraries/learning_models/src/learning_models/generative.py
# specifically from `DefaultGenerativeModels``
#
# WARNING: some of them are excluded from the original, commented down here on purpose.
# Try to keep the original order to make diffs more useful
# Also delete only the model if it has been deleted on the original
from pydantic import BaseModel
from pydantic import Field

import pytest
import re


class ModelInfo(BaseModel):
    test_rephrase: bool = True
    test_json: bool = True
    # Matches zone name
    zones_re: str | None = Field(
        description="Regex pattern to match zones name with. If none, matches all", default=None
    )

    def match_zone(self, zone_name: str) -> bool:
        return self.zones_re is None or re.match(self.zones_re, zone_name) is not None


ALL_LLMS: dict[str, ModelInfo] = {
    # "generative-multilingual-2023",        EXCLUDED because it's a legacy model, not available anymore
    # "chatgpt-azure-4-turbo",               DISCONTINUED
    "chatgpt-azure-4o": ModelInfo(),
    "chatgpt-azure-4o-mini": ModelInfo(),
    # "chatgpt-azure-o1-preview",            DISCONTINUED
    # "chatgpt-azure-o1-mini",               DISCONTINUED
    # "chatgpt-azure-o1",                    EXCLUDED because it almost always fails with timeouts
    "chatgpt-azure-o3-mini": ModelInfo(
        test_rephrase=False,  # Reasoning model
    ),
    "chatgpt-azure-5": ModelInfo(),
    "chatgpt-azure-5-mini": ModelInfo(),
    "chatgpt-azure-5-chat": ModelInfo(
        test_json=False,  # Structured output not working
    ),
    "chatgpt-azure-5-nano": ModelInfo(),
    "claude-3": ModelInfo(),
    # "claude-3-fast",                       DISCONTINUED
    "claude-3-5-fast": ModelInfo(),
    "claude-3-5-small": ModelInfo(),
    "claude-4-opus": ModelInfo(),
    "claude-4-sonnet": ModelInfo(),
    "gemini-2.0-flash-lite": ModelInfo(),
    "gemini-2.0-flash": ModelInfo(),
    "gemini-2.5-pro": ModelInfo(),
    "gemini-2.5-flash": ModelInfo(),
    "gemini-2.5-flash-lite": ModelInfo(),
    "mistral": ModelInfo(),
    # "azure-mistral",                       DISCONTINUED
    "chatgpt4o": ModelInfo(),
    "chatgpt4o-mini": ModelInfo(),
    # "chatgpt-o1-preview",                  DISCONTINUED
    # "chatgpt-o1-mini",                     DISCONTINUED
    "chatgpt-o1": ModelInfo(
        test_json=False,  # EXCLUDED because it almost always fails with timeouts
        test_rephrase=False,  # Reasoning model
    ),
    "chatgpt-o3-mini": ModelInfo(
        test_rephrase=False,  # Reasoning model
    ),
    "chatgpt-4.1": ModelInfo(),
    "chatgpt-5": ModelInfo(),
    "chatgpt-5-mini": ModelInfo(),
    "chatgpt-5-nano": ModelInfo(),
    "chatgpt-5-chat": ModelInfo(
        test_json=False,  # Structured output not working
    ),
    # "huggingface"                          EXCLUDED as not a model,just a driver, that needs a key to work
    "llama-3.2-90b-vision-instruct-maas": ModelInfo(
        test_json=False,  # Json functionality not operational
    ),
    "llama-4-maverick-17b-128e-instruct-maas": ModelInfo(
        test_json=False,  # Json functionality not operational
    ),
    "llama-4-scout-17b-16e-instruct-maas": ModelInfo(
        test_json=False,  # Json functionality not operational
    ),
    # "deepseek-reasoner",                   DISCONTINUED
    # "deepseek-chat",                       DISCONTINUED
    # "azure-deepseek-r1",                   EXCLUDED as it is too slow
    "azure-mistral-large-2": ModelInfo(),
    "gcp-claude-3-5-sonnet-v2": ModelInfo(),
    "gcp-claude-3-7-sonnet": ModelInfo(),
    # AWS claude models are available in all AWS-based regions except aws-il
    "aws-claude-3-7-sonnet": ModelInfo(zones_re="(aws-(?!il)|progress-).*"),
    "aws-claude-4-sonnet": ModelInfo(zones_re="(aws-(?!il)|progress-).*"),
    # The opus models are not available in europe
    "aws-claude-4-opus": ModelInfo(zones_re="(aws-(?!il|europe)|progress-).*"),
    "aws-claude-4-1-opus": ModelInfo(zones_re="(aws-(?!il|europe)|progress-).*"),
    # "openai-compatible",                   EXCLUDED as not a model,just a driver, that needs a key to work
    # "deepseek-chat-openai-compat"           EXCLUDED as not a model,just a driver, that needs a key to work
}


def model_zone_check(model: str, zone: str):
    if not ALL_LLMS[model].match_zone(zone):
        pytest.skip(f"Model {model} is not available in zone {zone}.")


REPHRASE_TEST_LLMS = [model_name for (model_name, model) in ALL_LLMS.items() if model.test_rephrase]
JSON_OUTPUT_TEST_LLMS = [model_name for (model_name, model) in ALL_LLMS.items() if model.test_json]

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
