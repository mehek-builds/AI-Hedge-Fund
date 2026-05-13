"""Wave 0 stubs -- FR-5.2 (DB-backed PER)."""
import os
import sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tests.conftest import requires_db
from rl.per_buffer import PERBuffer, Transition


@requires_db
def test_db_push():
    """FR-5.2: PERBuffer.push must write transition to rl_transitions hypertable."""
    buf = PERBuffer(maxlen=100)
    t = Transition(
        state=np.zeros(31, dtype=np.float32),
        action=np.array([0.5, 3], dtype=np.float32),
        reward=0.1,
        next_state=np.zeros(31, dtype=np.float32),
        done=False,
    )
    # After Wave 2, PERBuffer must expose push_to_db / persist hooks
    assert hasattr(buf, "push_to_db") or hasattr(buf, "add_persistent"), \
        "PERBuffer must expose DB persistence (push_to_db or add_persistent)"


def test_priority_sampling():
    """FR-5.2: Higher-priority transitions are returned more frequently."""
    buf = PERBuffer(maxlen=1000)
    for i in range(100):
        t = Transition(
            state=np.full(4, i, dtype=np.float32),
            action=np.array([0.0, 0], dtype=np.float32),
            reward=0.0,
            next_state=np.zeros(4, dtype=np.float32),
            done=False,
        )
        # td_error = i means transition i has priority proportional to i^alpha
        buf.add(t, td_error=float(i))
    counts = np.zeros(100)
    for _ in range(50):
        batch = buf.sample(32)
        for tr in batch.transitions:
            counts[int(tr.state[0])] += 1
    # High-priority (last 20) must be sampled more often than low-priority (first 20)
    assert counts[80:].sum() > counts[:20].sum()
