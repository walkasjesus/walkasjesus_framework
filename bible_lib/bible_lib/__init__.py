import os
from pathlib import Path

_ROOT_PATH = Path(os.path.abspath(os.path.dirname(__file__)))
_DATA_PATH = _ROOT_PATH / 'data'

from .bibles import Bibles
from .bible_books import BibleBooks
from .config import API_KEY
from .config import store_cache_every_number_of_hits
from .bible import Bible
from .bible_factory import BibleFactory



