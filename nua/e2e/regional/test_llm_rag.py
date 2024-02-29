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
        model="chatgpt-azure",
    )
    assert "Eudald" in generated.answer


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

    assert "Eudald" in generated.answer


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
    assert "Luis" in generated.answer


def test_llm_rag_nuclia_everest_v1(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="nuclia-everest-v1",
    )
    assert "Eudald" in generated.answer


def test_llm_rag_nuclia_mistral_small(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="mistral",
    )
    assert "Eudald" in generated.answer


def test_llm_rag_nuclia_mistral_large(nua_config):
    if "stashify" not in nua_config:
        # Lets only test on stashify as everest is not on prod
        return

    np = NucliaPredict()
    generated = np.rag(
        question="Which is the CEO of Nuclia?",
        context=[
            "Nuclia CTO is Ramon Navarro",
            "Eudald Camprubí is CEO at the same company as Ramon Navarro",
        ],
        model="azure-mistral",
    )
    assert "Eudald" in generated.answer
