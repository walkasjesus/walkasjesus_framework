import os
from pathlib import Path

_ROOT_PATH = Path(os.path.abspath(os.path.dirname(__file__)))
_DATA_PATH = _ROOT_PATH / 'data'

from .hsv_bibles import HsvBibles
from .hsv_bible_factory import HsvBibleFactory
