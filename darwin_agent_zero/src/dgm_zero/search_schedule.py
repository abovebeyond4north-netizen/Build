from __future__ import annotations

import random
from collections import defaultdict, deque
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar


T = TypeVar("T")


def round_robin_by_lineage(
    items: Iterable[T],
    *,
    lineage_key: Callable[[T], Hashable],
    rng: random.Random,
) -> list[T]:
    """Interleave candidate lineages before spending repeat budget on one lineage.

    The scheduler preserves every input exactly once. It randomizes lineage order
    and within-lineage order using the caller's deterministic RNG, then consumes
    one item from every non-empty lineage per round. A fixed population prefix
    therefore covers as many distinct lineages as possible before evaluating a
    second mutation from any lineage.
    """
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be random.Random")

    groups: dict[Hashable, list[T]] = defaultdict(list)
    for item in items:
        groups[lineage_key(item)].append(item)
    if not groups:
        return []

    keys = list(groups)
    rng.shuffle(keys)
    queues: dict[Hashable, deque[T]] = {}
    for key in keys:
        values = groups[key]
        rng.shuffle(values)
        queues[key] = deque(values)

    scheduled: list[T] = []
    active = keys
    while active:
        next_active: list[Hashable] = []
        for key in active:
            queue = queues[key]
            scheduled.append(queue.popleft())
            if queue:
                next_active.append(key)
        active = next_active
    return scheduled
