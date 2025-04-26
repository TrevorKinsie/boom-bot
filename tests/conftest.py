"""
Pytest fixtures and configuration.
"""
import pytest
import sys
import os
from pathlib import Path

# Add project root to path to ensure imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent))