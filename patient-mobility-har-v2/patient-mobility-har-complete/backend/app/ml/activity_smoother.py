"""
Short temporal smoothing of the Random Forest's per-frame class
probabilities. The classifier itself is unchanged and still decides every
frame from MediaPipe -> features -> Random Forest; this only stops the
DISPLAYED/recorded activity from flickering on single-frame errors
(mostly standing <-> walking, sitting <-> lying at transitions).

How it works:
  * keep the probability vectors of the last `window_sec` seconds
    (time-based, so it behaves the same at 10 or 30 fps);
  * the candidate label is the argmax of their MEAN probability (soft vote);
  * the shown label only switches if the candidate beats the current label's
    mean probability by `switch_margin` and reaches `min_confidence`
    (hysteresis) - a real, sustained change goes through within roughly
    half the window, a one-frame glitch does not;
  * if no person was seen for `max_gap_sec` the state resets.
It never invents a label: with no established label and confidence below
`min_confidence` it returns None.
"""

from collections import deque
from typing import Deque, Dict, Optional, Tuple


class ActivitySmoother:
    def __init__(
        self,
        window_sec: float = 1.0,
        min_confidence: float = 0.55,
        switch_margin: float = 0.10,
        max_gap_sec: float = 1.5,
    ):
        self.window_sec = window_sec
        self.min_confidence = min_confidence
        self.switch_margin = switch_margin
        self.max_gap_sec = max_gap_sec
        self._buffer: Deque[Tuple[float, Dict[str, float]]] = deque()
        self._current: Optional[str] = None

    def reset(self) -> None:
        self._buffer.clear()
        self._current = None

    def update(self, probabilities: Dict[str, float], timestamp_sec: float) -> Optional[Tuple[str, float]]:
        if self._buffer and timestamp_sec - self._buffer[-1][0] > self.max_gap_sec:
            self.reset()

        self._buffer.append((timestamp_sec, probabilities))
        while self._buffer and timestamp_sec - self._buffer[0][0] > self.window_sec:
            self._buffer.popleft()

        labels = probabilities.keys()
        mean = {lbl: sum(p.get(lbl, 0.0) for _, p in self._buffer) / len(self._buffer) for lbl in labels}
        best = max(mean, key=mean.get)

        if self._current is None:
            if mean[best] < self.min_confidence:
                return None
            self._current = best
        elif best != self._current:
            if mean[best] >= self.min_confidence and mean[best] >= mean.get(self._current, 0.0) + self.switch_margin:
                self._current = best

        return self._current, float(mean[self._current])
