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

    def test_no_compute_position_size_defined_in_backtest_modules(self):
        """Portfolio sizing must not be re-implemented in backtest modules.

        compute_position_size belongs in app.portfolio.pipeline, not backtest/.
        """
        for module_path in _get_all_backtest_module_paths():
            source = _get_python_source(module_path)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert not node.name.startswith("compute_position_size"), (
                        f"Portfolio sizing function '{node.name}' re-implemented in "
                        f"{module_path.name} — FR-6.2 forbids parallel portfolio logic"
                    )

    def test_no_portfolio_pipeline_logic_in_backtest_modules(self):
        """No portfolio pipeline functions should be redefined in backtest modules.

        Functions like apply_erp_cap, apply_mag7_cap, apply_stop_loss belong in
        app.portfolio.pipeline, not in any backtest module.
        """
        portfolio_pipeline_funcs = {
            "apply_erp_cap",
            "apply_mag7_cap",
            "apply_stop_loss",
            "size_position",
        }
        for module_path in _get_all_backtest_module_paths():
            source = _get_python_source(module_path)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in portfolio_pipeline_funcs, (
                        f"Portfolio logic '{node.name}' re-implemented in "
                        f"{module_path.name} — FR-6.2 forbids parallel portfolio logic"
                    )

    def test_single_definition_of_compute_signal_for_event(self):
        """compute_signal_for_event must have exactly one definition in the codebase.

        The production definition lives in app/signals/pipeline.py. Verifies
        no duplicate appears elsewhere in app/ (backtest or otherwise).
        """
        app_root = _BACKEND_ROOT / "app"
        definitions = []
        for py_file in app_root.rglob("*.py"):
            source = _get_python_source(py_file)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == "compute_signal_for_event":
                        definitions.append(str(py_file.relative_to(_BACKEND_ROOT)))
        assert len(definitions) == 1, (
            f"Expected exactly 1 definition of compute_signal_for_event, "
            f"found {len(definitions)}: {definitions}. "
            "FR-6.2: backtest must import from production, not redefine."
        )

    def test_replay_imports_fills_not_reimplemented(self):
        """replay.py must import fills from app.backtest.fills, not redefine fill logic.

        Simulated fill arithmetic must not be re-implemented inline in replay.py.
        """
        replay_path = _BACKTEST_PKG / "replay.py"
        source = _get_python_source(replay_path)
        # Must import simulate_fill from fills module
        assert "simulate_fill" in source, (
            "replay.py must import simulate_fill from app.backtest.fills (FR-6.2)"
        )
        # Must not define its own fill calculation function
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert (
                    not node.name.startswith("simulate_fill")
                    and node.name != "fill_order"
                ), (
                    f"Fill logic '{node.name}' defined inline in replay.py — "
                    "import from app.backtest.fills instead (FR-6.2)"
                )

    def test_no_select_action_defined_in_backtest_modules(self):
        """SAC select_action must not be re-implemented in backtest modules.

        Action selection belongs in rl.sac_agent.SACEnsemble.select_action_per_agent,
        not in any backtest module.
        """
        for module_path in _get_all_backtest_module_paths():
            source = _get_python_source(module_path)
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert not node.name.startswith("select_action"), (
                        f"SAC select_action re-implemented in backtest module "
                        f"{module_path.name} — FR-6.2 forbids parallel RL logic"
                    )
