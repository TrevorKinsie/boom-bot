"""
Pytest fixtures and configuration.
"""
import os
import sys
import tempfile
from pathlib import Path

# Isolate persistent casino data to a per-run temporary directory so tests
# never write into the repository's working data store. This must be set
# before any boombot module is imported, since core.config resolves DATA_DIR at
# import time.
os.environ.setdefault("BOT_DATA_DIR", tempfile.mkdtemp(prefix="boombot_test_"))

# Add project root to path to ensure imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent))