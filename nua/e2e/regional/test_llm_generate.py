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


def test_llm_generate_claude(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="claude-3")
    assert "Barcelona" in generated.answer


def test_llm_generate_gemini(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="gemini-1-5-pro")
    assert "Barcelona" in generated.answer
