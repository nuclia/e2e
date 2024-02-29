from nuclia.sdk.predict import NucliaPredict


def test_llm_generate_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="chatgpt-azure-3"
    )
    assert "Barcelona" in generated.answer


def test_llm_generate_azure_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="chatgpt-azure")
    assert "Barcelona" in generated.answer


def test_llm_generate_anthropic(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="anthropic")
    assert "Barcelona" in generated.answer


def test_llm_generate_palm(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="gemini-pro")
    assert "Barcelona" in generated.answer


def test_llm_generate_nuclia_everest_v1(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="nuclia-everest-v1"
    )
    assert "Barcelona" in generated.answer


def test_llm_generate_nuclia_mistral_small(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="mistral")
    assert "Barcelona" in generated.answer


def test_llm_generate_nuclia_mistral_large(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="azure-mistral")
    assert "Barcelona" in generated.answer
