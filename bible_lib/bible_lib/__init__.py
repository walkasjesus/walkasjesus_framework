import os
from pathlib import Path

_ROOT_PATH = Path(os.path.abspath(os.path.dirname(__file__)))
_DATA_PATH = _ROOT_PATH / 'data'

from .bibles import Bibles
from .bible_books import BibleBooks
from .config import API_KEY
from .bible import Bible
from .bible_factory import BibleFactory



