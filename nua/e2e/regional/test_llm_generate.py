from nuclia.sdk.predict import NucliaPredict


def test_llm_generate_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="chatgpt")
    assert b"Barcelona" in generated


def test_llm_generate_azure_chatgpt(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="chatgpt-azure")
    assert b"Barcelona" in generated


def test_llm_generate_anthropic(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="anthropic")
    assert b"Barcelona" in generated


def test_llm_generate_palm(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="palm")
    assert b"Barcelona" in generated


def test_llm_generate_cohere(nua_config):
    np = NucliaPredict()
    generated = np.generate("Which is the capital of Catalonia?", model="cohere")
    assert b"Barcelona" in generated


def test_llm_generate_nuclia_atlas_v1(nua_config):
    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="nuclia-atlas-v1"
    )
    assert b"Barcelona" in generated


def test_llm_generate_nuclia_etna_v1(nua_config):
    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="nuclia-etna-v1"
    )
    assert b"Barcelona" in generated


def test_llm_generate_nuclia_everest_v1(nua_config):
    np = NucliaPredict()
    generated = np.generate(
        "Which is the capital of Catalonia?", model="nuclia-everest-v1"
    )
    assert b"Barcelona" in generated
