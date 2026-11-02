"""Ingest stage: documents + Mongo catalog -> Chroma index (data/chroma_db).

python -m ingest.main
"""

import logging

from src.config import load_settings
from src.ingest import build_index


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    build_index(load_settings())


if __name__ == "__main__":
    main()
