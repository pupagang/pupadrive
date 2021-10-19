import logging
from importlib import metadata
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

__version__ = metadata.version(__name__)

logger = logging.getLogger()

formatter = logging.Formatter(
    "%(levelname)s %(asctime)s - %(name)s - %(message)s")

fh = RotatingFileHandler(f"{__name__}.log", maxBytes=10 ** 6, backupCount=0)
fh.setFormatter(formatter)
fh.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.INFO)

logger.setLevel(logging.INFO)
logger.handlers = []
logger.addHandler(fh)
logger.addHandler(ch)

__all__ = ["__version__"]

load_dotenv()
