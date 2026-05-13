"""Prioritized Experience Replay buffer for SAC ensemble."""

from __future__ import annotations

import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import NamedTuple


class Transition(NamedTuple):
    state: np.ndarray
    action: np.ndarray
    reward: float
    next_state: np.ndarray
    done: bool


@dataclass
class SampleBatch:
    transitions: list[Transition]
    indices: np.ndarray
    weights: np.ndarray   # importance-sampling weights


class SumTree:
    """Binary sum tree for O(log n) priority sampling."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._tree = np.zeros(2 * capacity, dtype=np.float64)
        self._data: list[Transition | None] = [None] * capacity
        self._write = 0
        self._n = 0

    @property
    def total(self) -> float:
        return float(self._tree[1])

    def _propagate(self, idx: int, delta: float) -> None:
        parent = idx >> 1
        while parent >= 1:
            self._tree[parent] += delta
            parent >>= 1

    def add(self, priority: float, transition: Transition) -> None:
        leaf = self._write + self._capacity
        self._data[self._write] = transition
        self.update(leaf, priority)
        self._write = (self._write + 1) % self._capacity
        self._n = min(self._n + 1, self._capacity)

    def update(self, leaf_idx: int, priority: float) -> None:
        delta = priority - self._tree[leaf_idx]
        self._tree[leaf_idx] = priority
        self._propagate(leaf_idx, delta)

    def retrieve(self, s: float) -> tuple[int, float, Transition | None]:
        idx = 1
        while idx < self._capacity:
            left = idx << 1
            if s <= self._tree[left]:
                idx = left
            else:
                s -= self._tree[left]
                idx = left + 1
        data_idx = idx - self._capacity
        return idx, self._tree[idx], self._data[data_idx]

    def __len__(self) -> int:
        return self._n


class PERBuffer:
    """
    Prioritized Experience Replay with recency-weighted priorities.

    priority(i) = (|td_error| + eps) ** alpha * recency_weight(i)
    sampling prob P(i) = priority(i) / sum(priorities)
    IS weight w(i) = (1 / N*P(i)) ** beta, normalized by max weight
    """

    def __init__(
        self,
        maxlen: int = 50_000,
        alpha: float = 0.6,
        beta_start: float = 0.4,
        beta_end: float = 1.0,
        beta_anneal_steps: int = 10_000,
        eps: float = 1e-6,
        decay_lambda: float = 0.001,
        engine=None,  # Optional SQLAlchemy engine for DB-backed PER (FR-5.2)
    ) -> None:
        self._tree = SumTree(maxlen)
        self._alpha = alpha
        self._beta_start = beta_start
        self._beta_end = beta_end
        self._beta_anneal_steps = beta_anneal_steps
        self._eps = eps
        self._decay_lambda = decay_lambda
        self._step = 0
        self._max_priority = 1.0
        self._timestamps: deque[int] = deque(maxlen=maxlen)
        self._engine = engine  # Optional SQLAlchemy engine for DB-backed PER (FR-5.2)

    @property
    def beta(self) -> float:
        t = min(self._step / max(self._beta_anneal_steps, 1), 1.0)
        return self._beta_start + t * (self._beta_end - self._beta_start)

    def recency_weight(self, age: int) -> float:
        return float(np.exp(-self._decay_lambda * age))

    def add(self, transition: Transition, td_error: float | None = None) -> None:
        priority = self._max_priority if td_error is None else self._priority(td_error, age=0)
        self._tree.add(priority, transition)
        self._timestamps.append(self._step)
        self._step += 1

    def _priority(self, td_error: float, age: int) -> float:
        base = (abs(td_error) + self._eps) ** self._alpha
        return base * self.recency_weight(age)

    def sample(self, batch_size: int) -> SampleBatch:
        if len(self._tree) == 0:
            raise RuntimeError("Cannot sample from empty buffer")

        n = min(batch_size, len(self._tree))
        segment = self._tree.total / n

        transitions: list[Transition] = []
        indices: list[int] = []
        probs: list[float] = []

        for i in range(n):
            lo, hi = segment * i, segment * (i + 1)
            s = np.random.uniform(lo, hi)
            leaf_idx, priority, transition = self._tree.retrieve(s)
            if transition is None:
                continue
            indices.append(leaf_idx)
            probs.append(priority / self._tree.total)
            transitions.append(transition)

        n_sampled = len(transitions)
        weights = np.array(
            [(1.0 / (len(self._tree) * max(p, 1e-10))) ** self.beta for p in probs],
            dtype=np.float32,
        )
        weights /= weights.max()

        return SampleBatch(
            transitions=transitions,
            indices=np.array(indices, dtype=np.int64),
            weights=weights,
        )

    def hydrate_from_db(self, agent_id: int = 0, limit: int = 50_000) -> int:
        """Load top-priority transitions from DB into SumTree on startup (FR-5.2).

        Returns number of transitions loaded. No-op stub when engine is None
        or DB is unavailable -- full implementation coordinated with Plan 03.
        """
        if self._engine is None:
            return 0
        try:
            from rl.db_per import fetch_top_priority
            rows = fetch_top_priority(self._engine, agent_id=agent_id, limit=limit)
            for row in rows:
                self.add(row, td_error=None)
            return len(rows)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "hydrate_from_db failed (DB unavailable?): %s", exc
            )
            return 0

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
        for idx, td_err in zip(indices, td_errors):
            age = self._step - self._timestamps[idx - self._tree._capacity] if len(self._timestamps) > idx - self._tree._capacity else 0
            priority = self._priority(float(td_err), age=max(age, 0))
            self._tree.update(int(idx), priority)
            self._max_priority = max(self._max_priority, priority)

    def __len__(self) -> int:
        return len(self._tree)
