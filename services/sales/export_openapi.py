"""Writes this service's OpenAPI document to openapi.yaml, from the routes and models in the code.

    python export_openapi.py

Run it after changing an endpoint and commit openapi.yaml with the change: tests/test_openapi.py fails when the
committed file no longer matches the code, so the document can never silently drift from the API (A2 §8a).
It is a development tool: the Dockerfile does not copy it into the image.
"""
from pathlib import Path

import yaml

from app import app

OPENAPI_FILE = Path(__file__).resolve().parent / "openapi.yaml"


def write():
    OPENAPI_FILE.write_text(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True, width=120),
                            encoding="utf-8")


if __name__ == "__main__":
    write()
    print(f"Wrote {OPENAPI_FILE.name}")
