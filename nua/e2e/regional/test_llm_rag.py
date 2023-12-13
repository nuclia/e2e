from nuclia.sdk.predict import NucliaPredict


def test_llm_rag_chatgpt_openai(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt",
    )
    assert b"CEO of Nuclia is Eudald" in generated


def test_llm_rag_chatgpt_azure(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure",
    )
    assert b"CEO of Nuclia is Eudald" in generated


def test_llm_rag_anthropic(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="anthropic",
    )
    assert b"Eudald" in generated


def test_llm_rag_palm(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="palm",
    )
    assert b"Eudald" in generated


def test_llm_rag_cohere(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="cohere",
    )
    assert b"Eudald" in generated


def test_llm_rag_nuclia_atlas_v1(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="nuclia-atlas-v1",
    )
    assert b"Eudald" in generated


def test_llm_rag_nuclia_etna_v1(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="nuclia-etna-v1",
    )
    assert b"Eudald" in generated


def test_llm_rag_nuclia_everest_v1(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="nuclia-everest-v1",
    )
    assert b"Eudald" in generated
