from typing import Dict


class PathCounter:
    def __init__(self) -> None:
        self._counters: Dict[int, int] = {}

    def next(self, level: int) -> str:
        self._counters[level] = self._counters.get(level, 0) + 1
        for l in list(self._counters.keys()):
            if l > level:
                del self._counters[l]
        parts = [f"{self._counters.get(i, 0):03d}" for i in range(1, level + 1)]
        return ".".join(parts)
