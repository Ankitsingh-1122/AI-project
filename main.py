import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.join(_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
