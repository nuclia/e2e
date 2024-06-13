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
