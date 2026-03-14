import sys
import logging
import warnings
from pathlib import Path

# Suppress SQLAlchemy/aiosqlite GC cleanup messages (logging + warnings).
# These are harmless for a CLI that exits after each command.
logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", message=".*non-checked-in connection.*")
warnings.filterwarnings("ignore", message=".*garbage collector.*")
try:
    from sqlalchemy.exc import SAWarning
    warnings.filterwarnings("ignore", category=SAWarning)
except ImportError:
    pass

# Make `app` (backend/app/...) importable from cli/ code
_backend = Path(__file__).resolve().parent.parent / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
