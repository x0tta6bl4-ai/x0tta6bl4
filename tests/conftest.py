"""Pytest configuration for x0tta6bl4.

Ensures that the project root is on sys.path so imports like `from src...` work
in unit tests regardless of the working directory.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
