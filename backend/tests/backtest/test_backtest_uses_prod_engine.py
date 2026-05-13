"""Tests for FR-6.2: no parallel backtest-only signal implementations.

Grep-based AST inspection to verify that:
1. backtest/replay.py imports from production modules
2. No signal computation functions are defined in backtest/ modules
3. The production signal pipeline and SAC ensemble are the only code paths
"""

import ast
import pathlib


# Backend root
_BACKEND_ROOT = pathlib.Path(__file__).parent.parent.parent
_BACKTEST_PKG = _BACKEND_ROOT / "app" / "backtest"


def _get_python_source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_all_backtest_module_paths() -> list[pathlib.Path]:
    return list(_BACKTEST_PKG.glob("*.py"))


class TestNoParallelSignalImplementation:
    """FR-6.2: backtest must use production signal/ensemble code, not re-implement it."""

    def test_replay_imports_production_signal_pipeline(self):
        """replay.py must import from app.signals.pipeline, not define its own."""
        replay_path = _BACKTEST_PKG / "replay.py"
        assert replay_path.exists(), "replay.py must exist in app/backtest/"

        source = _get_python_source(replay_path)
        assert "app.signals.pipeline" in source or "signals.pipeline" in source, (
            "replay.py must import from production signal pipeline (FR-6.2)"
        )

    def test_replay_imports_macro_loader(self):
        """replay.py must import from app.portfolio.macro_loader for macro score."""
        replay_path = _BACKTEST_PKG / "replay.py"
        source = _get_python_source(replay_path)
        assert "macro_loader" in source, (
            "replay.py must import production macro_loader (FR-6.2)"
        )

    def test_no_compute_signal_defined_in_backtest_modules(self):
        """No function named compute_signal_* should be defined in backtest/ modules."""
        for module_path in _get_all_backtest_module_paths():
            source = _get_python_source(module_path)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert not node.name.startswith("compute_signal"), (
                        f"Backtest-only signal function '{node.name}' found in "
                        f"{module_path.name} — FR-6.2 forbids parallel signal logic"
                    )

    def test_no_eps_gap_defined_in_backtest_modules(self):
        """eps_gap() must not be re-implemented in backtest modules."""
        for module_path in _get_all_backtest_module_paths():
            source = _get_python_source(module_path)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name != "eps_gap", (
                        f"eps_gap() re-implemented in backtest module {module_path.name} "
                        "— FR-6.2 forbids parallel signal logic"
                    )

    def test_replay_uses_rl_sac_agent_import(self):
        """replay.py must reference rl.sac_agent or SACEnsemble for sizing."""
        replay_path = _BACKTEST_PKG / "replay.py"
        source = _get_python_source(replay_path)
        assert "SACEnsemble" in source or "sac_agent" in source, (
            "replay.py must use production SACEnsemble for position sizing (FR-6.2)"
        )

    def test_replay_uses_moe_controller(self):
        """replay.py must reference MoEController for multi-agent blending."""
        replay_path = _BACKTEST_PKG / "replay.py"
        source = _get_python_source(replay_path)
        assert "MoEController" in source or "moe_controller" in source, (
            "replay.py must use production MoEController (FR-6.2)"
        )
