"""conftest.py for RL tests — adds project root to sys.path so rl.* imports work."""
import os
import sys

# Add the repo root (two levels above backend/) to the path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
