import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.web.main import app  # noqa: E402

__all__ = ["app"]
