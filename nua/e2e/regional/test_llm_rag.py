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
    
    keywords ="CEO Nuclia Eudald".split()
    assert all([word in generated for word in keywords])


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
    keywords ="CEO Nuclia Eudald".split()
    assert all([word in generated for word in keywords])


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
    
    keywords ="CEO Nuclia Eudald".split()
    assert all([word in generated for word in keywords])


def test_llm_rag_palm(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="gemini-pro",
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
