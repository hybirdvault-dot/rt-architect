"""Allow ``python -m rtarch`` in addition to the ``rtarch`` console script."""

from .cli import app

if __name__ == "__main__":
    app()
