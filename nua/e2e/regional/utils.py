from pathlib import Path
from dataclasses import dataclass

FILE_PATH = f"{Path(__file__).parent.parent}/assets/"


def define_path(file: str):
    return FILE_PATH + file


@dataclass
class TestConfig:
    domain: str
    config_path: str
