"""Static deploy-gate tests for Phase 5 (FR-5.7).

These tests protect the "manual deploy only" invariant for the rl_trainer
Railway service. They are unit-only (no DB, no network) and run in every
PR - a regression where someone accidentally adds rl_trainer to docker-build
will fail CI immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def test_railway_rl_trainer_manual_deploy():
    """FR-5.7: railway.toml rl_trainer service must have deployTrigger = 'manual'."""
    content = _read("railway.toml")
    # Find the rl_trainer service block
    m = re.search(
        r'\[\[services\]\][^\[]*?name\s*=\s*"rl_trainer"[^\[]*',
        content,
        re.DOTALL,
    )
    assert m is not None, "rl_trainer service block missing from railway.toml"
    block = m.group(0)
    assert 'deployTrigger = "manual"' in block, (
        "rl_trainer must have deployTrigger = \"manual\" - auto-deploy on push to main "
        "kills in-progress training jobs (CLAUDE.md, railway.toml)."
    )


def test_railway_rl_trainer_uses_new_module():
    """railway.toml rl_trainer startCommand must point at worker.flows.rl_trainer (Plan 05)."""
    content = _read("railway.toml")
    assert "python -m worker.flows.rl_trainer" in content, (
        "rl_trainer startCommand must be `python -m worker.flows.rl_trainer` "
        "(Plan 05 updated this from the legacy `python -m app.rl.trainer`)."
    )


def test_ci_excludes_rl_trainer_from_docker_build():
    """CLAUDE.md: rl_trainer image is not built in CI (manual-deploy-only)."""
    content = _read(".github/workflows/ci.yml")
    # Heuristic: no docker/build-push-action step has tag containing 'rl-trainer' or 'rl_trainer'
    bad_patterns = [
        r"tags:\s*pead-rl-trainer",
        r"context:\s*\./rl",
        r"name:\s*Build\s+rl[_-]trainer",
    ]
    for pat in bad_patterns:
        assert re.search(pat, content) is None, (
            f"CI yml contains rl_trainer build step matching {pat!r} - "
            "rl_trainer must remain manual-deploy-only (CLAUDE.md)."
        )


def test_ci_does_not_deploy_to_railway_rl_trainer():
    """No CI job may invoke `railway up --service rl_trainer` (manual only)."""
    content = _read(".github/workflows/ci.yml")
    assert "railway up --service rl_trainer" not in content
    assert "railway deploy --service rl_trainer" not in content
