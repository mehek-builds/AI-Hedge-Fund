"""Static deploy gate tests -- NFR-4: rl_trainer must not appear in auto-deploy steps.

These tests run without a database. They are regression guards: if anyone accidentally
adds rl_trainer back to the cd.yml deploy step or changes deployTrigger in railway.toml,
these tests fail in CI.

No @requires_db needed. No pytest.mark.asyncio needed.
"""
from pathlib import Path

import pytest

# Resolve repo root from the test file location:
# backend/tests/test_deploy_gate.py -> parent=tests -> parent=backend -> parent=repo root
REPO_ROOT = Path(__file__).parent.parent.parent


def test_rl_trainer_excluded_from_cd_workflow():
    """Assert that rl_trainer does not appear in any 'railway up' command in cd.yml.

    NFR-4: The rl_trainer service must be manual-deploy-only. Auto-deploy on push to
    main would kill in-progress training jobs. This test catches any accidental
    re-addition of rl_trainer to the auto-deploy step.
    """
    cd_yml = REPO_ROOT / ".github" / "workflows" / "cd.yml"

    if not cd_yml.exists():
        pytest.skip("cd.yml not found - skipping deploy gate check")

    content = cd_yml.read_text()

    railway_up_lines = [
        line for line in content.splitlines() if "railway up" in line
    ]

    assert len(railway_up_lines) > 0, (
        "No 'railway up' commands found in cd.yml. "
        "Expected at least one service deploy command."
    )

    for line in railway_up_lines:
        # Strip inline comments so we only check the actual command
        command_part = line.split("#")[0]
        assert "rl_trainer" not in command_part, (
            f"rl_trainer found in railway up command: {line!r}\n"
            "rl_trainer must be manual-deploy-only (NFR-4). "
            "Remove it from cd.yml deploy step and use "
            "'railway up --service rl_trainer' manually instead."
        )


def test_rl_trainer_deploy_trigger_is_manual():
    """Assert that railway.toml sets deployTrigger = 'manual' for rl_trainer.

    NFR-4: Two independent guards prevent rl_trainer from auto-deploying:
    1. cd.yml does not include rl_trainer in any 'railway up' step (tested above).
    2. railway.toml sets deployTrigger = 'manual' for the rl_trainer service (this test).

    If both guards are present, an accidental push to main will NOT trigger an rl_trainer
    deploy that could kill an in-progress training job.
    """
    toml_path = REPO_ROOT / "railway.toml"

    if not toml_path.exists():
        pytest.skip("railway.toml not found - skipping deploy trigger check")

    content = toml_path.read_text()

    assert "rl_trainer" in content, (
        "rl_trainer service not found in railway.toml. "
        "Expected a [[services]] block with name = 'rl_trainer'."
    )

    assert 'deployTrigger = "manual"' in content, (
        "rl_trainer deployTrigger must be 'manual' in railway.toml (NFR-4). "
        'Found content does not contain: deployTrigger = "manual"\n'
        "Add deployTrigger = \"manual\" to the rl_trainer service block in railway.toml."
    )
