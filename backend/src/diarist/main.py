"""Uvicorn entrypoint: `python -m diarist.main`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "diarist.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        workers=1,  # a single worker matches the single shared GPU slot
    )


if __name__ == "__main__":
    main()
