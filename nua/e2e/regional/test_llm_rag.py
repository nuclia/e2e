from nuclia.sdk.predict import NucliaPredict


def test_llm_rag_chatgpt_openai(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure-3",
    )
    
    assert b"Eudald" in generated


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
    assert b"Eudald" in generated


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
            "Nuclia CTO is leo",
            "Luis is CEO at the same company as leo",
        ],
        model="gemini-pro",
    )
    assert b"Luis" in generated


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
