from nuclia.sdk.predict import NucliaPredict


# def test_llm_citations_everest(nua_config, benchmark):
#     np = NucliaPredict()
#     embed = np.generate("Who is the CEO of Nuclia?", model="everest")
#     assert embed.time > 0
#     assert len(embed.tokens) == 1


# def test_llm_citations_azure_chatgpt(nua_config, benchmark):
#     np = NucliaPredict()
#     embed = np.generate("Who is the CEO of Nuclia?", model="chatgpt")
#     assert embed.time > 0
#     assert len(embed.tokens) == 1
