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

    assert "Eudald" in generated.answer


def test_llm_rag_chatgpt_azure(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="chatgpt-azure-4o",
    )
    assert "Eudald" in generated.answer


def test_llm_rag_claude(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="claude-3",
    )

    assert "Eudald" in generated.answer


def test_llm_rag_gemini(nua_config):
    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is leo",
            "Luis is CEO at the same company as leo",
        ],
        model="gemini-1-5-pro",
    )
    assert "Luis" in generated.answer
