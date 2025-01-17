from pathlib import Path

ASSETS_FILE_PATH = Path(__file__).parent.joinpath("assets")


def get_asset_file_path(file: str):
    return str(ASSETS_FILE_PATH.joinpath(file))
