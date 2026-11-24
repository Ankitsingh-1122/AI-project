import os
import sys

# Ensure backend directory is in sys.path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_dir = os.path.join(_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.app.main import app

__all__ = ["app"]
