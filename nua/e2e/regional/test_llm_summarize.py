from nuclia.sdk.predict import AsyncNucliaPredict
import pytest
from nuclia.lib.nua import AsyncNuaClient

DATA = {
    "barcelona": "Barcelona (pronunciat en català central, [bərsəˈlonə]) és una ciutat i metròpoli a la costa mediterrània de la península Ibèrica. És la capital de Catalunya,[1] així com de la comarca del Barcelonès i de la província de Barcelona, i la segona ciutat en població i pes econòmic de la península Ibèrica,[2][3] després de Madrid. El municipi creix sobre una plana encaixada entre la serralada Litoral, el mar Mediterrani, el riu Besòs i la muntanya de Montjuïc. La ciutat acull les seus de les institucions d'autogovern més importants de la Generalitat de Catalunya: el Parlament de Catalunya, el President i el Govern de la Generalitat. Pel fet d'haver estat capital del Comtat de Barcelona, rep sovint el sobrenom de Ciutat Comtal. També, com que ha estat la ciutat més important del Principat de Catalunya des d'època medieval, rep sovint el sobrenom o títol de cap i casal.[4]",  # noqa
    "manresa": "Manresa és un municipi i una ciutat de Catalunya, capital de la comarca del Bages i de la Catalunya central. Està situada al pla de Bages, prop de l'angle on conflueixen els rius Llobregat i Cardener. Amb una població de 76.250 habitants el 2018,[1] és la ciutat més poblada del Bages i de la Catalunya Central. Es troba a 65 km al nord de Barcelona, i marca el límit entre l'àrea industrial al voltant de Barcelona i l'àrea rural del nord. La ciutat forma un nus molt important de comunicacions, accentuat amb l'eix del Llobregat i l'eix transversal, entre la muntanya i el mar, entre les planes interiors de l'Urgell i la Segarra i les comarques orientals del país. Quant a l'economia, Manresa destaca en la indústria tèxtil, química i maquinària, si bé en les últimes dècades ha substituït la indústria pel comerç. La ciutat també destaca pel seu conjunt medieval, amb els ponts damunt el riu Cardener i la seva catedral d'estil gòtic. A més, en aquesta ciutat també es troben esglésies d'estil barroc, així com interessants edificacions modernistes.",  # noqa
}

DATA_COFFEE = {
    "Flat white": """A flat white is a coffee drink consisting of espresso with microfoam (steamed milk with small, fine bubbles and a glossy or velvety consistency). It generally has a higher proportion of espresso to milk than a caffè latte, and a thinner layer of microfoam than a cappuccino. Although the term "flat white" was used in the United Kingdom to describe a type of espresso-based drink in the 1960s, the modern flat white was developed in Australia and New Zealand.

Description
Anette Moldvaer states that a flat white consists of a double espresso (50 ml/1.5 fl oz) and about 130 ml (4 fl oz) of steamed milk with a 5 mm (0.25 inch) layer of microfoam.[1] According to a survey of industry commentators, a flat white has a thin layer of microfoam (hence the 'flat' in flat white), as opposed to the significantly thicker layer of foam in a traditional cappuccino.[2]

The recipe for a flat white, however, varies between regions and cafés. In Australia a flat white is served in a ceramic mug, usually of the same volume (200 ml, 7.0 imp fl oz) as a latte glass. However, some Australian cafés will top a latte with extra froth, while others may pour a flat white slightly shorter.[3] New Zealand flat whites are more commonly served in a tulip shaped cup (165 ml, 5.8 imp fl oz). In both Australia and New Zealand, there is a generally accepted difference between lattes and flat whites in the ratio of milk to coffee and the consistency of the milk due to the way the milk is heated.""",
    "Macchiato": """Caffè macchiato (Italian pronunciation: , sometimes called espresso macchiato,[1][2] is an espresso coffee drink with a small amount of milk, usually foamed. In Italian, macchiato means "stained" or "spotted", so the literal translation of caffè macchiato is "stained coffee" or "marked coffee".
History
The origin of the name "macchiato" stems from baristas needing to show the serving waiters the difference between an espresso and an espresso with a tiny bit of milk in it; the latter was "marked". The idea is reflected in the Portuguese name for the drink: café pingado, meaning "coffee with a drop".[3]

Preparation
See also: latte macchiato and caffè latte
The caffè macchiato has the highest ratio of espresso to milk of any drink made with those ingredients. The intent is that the milk moderates, rather than overwhelms, the taste of the coffee while adding a touch of sweetness. The drink is typically prepared by pouring a small amount of steamed milk directly into a single shot of espresso.[4] One recipe calls for 5–10 g (1–2 teaspoons) of milk heated to 60–66 °C (140–150 °F).[5]

Regional variants
In Australia the drink is referred to as a macchiato and has some variants.[6] A traditional long macchiato is usually a double shot of espresso with a dash of textured milk and most of the glass left empty. In Perth, a 'long mac topped up' is usually ordered, which is a double shot of espresso with the glass filled with textured milk. In Melbourne, it is a double-shot of espresso, a glass half-filled with water, and a dash of textured milk on top.[7]""",
}


@pytest.mark.asyncio_cooperative
async def test_summarize_chatgpt(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()
    embed = await np.summarize(DATA, model="chatgpt4o", nc=nua_config)
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


@pytest.mark.asyncio_cooperative
async def test_summarize_azure_chatgpt(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()
    embed = await np.summarize(DATA, model="chatgpt-azure-4o", nc=nua_config)
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


@pytest.mark.asyncio_cooperative
async def test_summarize_claude(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()
    embed = await np.summarize(DATA_COFFEE, model="claude-3-fast", nc=nua_config)
    # changed to partial summaries since anthropic is not consistent in the global summary at all
    assert "flat white" in embed.resources["Flat white"].summary.lower()
    assert "macchiato" in embed.resources["Macchiato"].summary.lower()
