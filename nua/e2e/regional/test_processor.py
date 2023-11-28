from pathlib import Path
from nuclia.sdk.process import NucliaProcessing

FILE_PATH = f"{Path(__file__).parent.parent}/assets/"


def define_path(file: str):
    return FILE_PATH + file


def test_pdf(nua_config):
    path = define_path("2310.14587.pdf")
    nc = NucliaProcessing()
    nc.process_file(path)


def test_activity(nua_config):
    nc = NucliaProcessing()
    nc.status()
