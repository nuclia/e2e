from nuclia.sdk.predict import NucliaPredict


DATA = {
    "barcelona": "Barcelona (pronunciat en català central, [bərsəˈlonə]) és una ciutat i metròpoli a la costa mediterrània de la península Ibèrica. És la capital de Catalunya,[1] així com de la comarca del Barcelonès i de la província de Barcelona, i la segona ciutat en població i pes econòmic de la península Ibèrica,[2][3] després de Madrid. El municipi creix sobre una plana encaixada entre la serralada Litoral, el mar Mediterrani, el riu Besòs i la muntanya de Montjuïc. La ciutat acull les seus de les institucions d'autogovern més importants de la Generalitat de Catalunya: el Parlament de Catalunya, el President i el Govern de la Generalitat. Pel fet d'haver estat capital del Comtat de Barcelona, rep sovint el sobrenom de Ciutat Comtal. També, com que ha estat la ciutat més important del Principat de Catalunya des d'època medieval, rep sovint el sobrenom o títol de cap i casal.[4]",  # noqa
    "manresa": "Manresa és un municipi i una ciutat de Catalunya, capital de la comarca del Bages i de la Catalunya central. Està situada al pla de Bages, prop de l'angle on conflueixen els rius Llobregat i Cardener. Amb una població de 76.250 habitants el 2018,[1] és la ciutat més poblada del Bages i de la Catalunya Central. Es troba a 65 km al nord de Barcelona, i marca el límit entre l'àrea industrial al voltant de Barcelona i l'àrea rural del nord. La ciutat forma un nus molt important de comunicacions, accentuat amb l'eix del Llobregat i l'eix transversal, entre la muntanya i el mar, entre les planes interiors de l'Urgell i la Segarra i les comarques orientals del país. Quant a l'economia, Manresa destaca en la indústria tèxtil, química i maquinària, si bé en les últimes dècades ha substituït la indústria pel comerç. La ciutat també destaca pel seu conjunt medieval, amb els ponts damunt el riu Cardener i la seva catedral d'estil gòtic. A més, en aquesta ciutat també es troben esglésies d'estil barroc, així com interessants edificacions modernistes.",  # noqa
}


def test_summarize_chatgpt(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="chatgpt")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_azure_chatgpt(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="chatgpt-azure")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_anthropic(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="anthropic")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_palm(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="palm")
    assert "manresa" in embed.summary
    assert "barcelona" in embed.summary


def test_summarize_cohere(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="cohere")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_nuclia_atlas_v1(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="nuclia-atlas-v1")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_nuclia_etna_v1(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="nuclia-etna-v1")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary


def test_summarize_nuclia_everest_v1(nua_config):
    np = NucliaPredict()
    embed = np.summarize(DATA, model="nuclia-everest-v1")
    assert "Manresa" in embed.summary
    assert "Barcelona" in embed.summary
