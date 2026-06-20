"""Roxy mascot widget — animated ASCII art for agent states."""

from __future__ import annotations

from textual.widgets import Static
from textual import work

# ASCII art frames
IDLE_FRAME_0 = r"""
     /\_/\
   _/ o o \_
  /  \  ~  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
"""

IDLE_FRAME_1 = r"""
     /\_/\
   _/ o o \_
  /  \  -  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
"""

THINKING_FRAMES = [
    r"""
     /\_/\
   _/ o o \_
  /  \  ·  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
    r"""
     /\_/\
   _/ - - \_
  /  \  ·  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
    r"""
     /\_/\
   _/ o o \_
  /  \  ·  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
]

TYPING_FRAMES = [
    r"""
     /\_/\
   _/ > < \_
  /  \  ^  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
    r"""
     /\_/\
   _/ o o \_
  /  \  ^  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
]

MAGIC_FRAMES = [
    r"""
     /\_/\
   _/ * * \_
  /  \  ~  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
    r"""
     /\_/\
   _/ o o \_
  /  \  *  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
""",
]


class MascotWidget(Static):
    """Animated Roxy mascot that responds to agent state.

    States: idle, thinking, typing, magic, hop.
    Uses set_interval to cycle ASCII frames.
    """

    DEFAULT_CSS = """
    MascotWidget {
        width: 20;
        height: 8;
        margin: 0 1;
        color: $text;
    }
    """

    FRAMES = {
        "idle": [IDLE_FRAME_0, IDLE_FRAME_1],
        "thinking": THINKING_FRAMES,
        "typing": TYPING_FRAMES,
        "magic": MAGIC_FRAMES,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state: str = "idle"
        self._frame_index: int = 0
        self._timer: work.Worker | None = None

    def on_mount(self) -> None:
        """Start idle animation."""
        self._start_animation("idle")

    def set_state(self, state: str) -> None:
        """Switch to a new state: idle, thinking, typing, magic."""
        if state == self._state:
            return
        self._state = state

        # Different speeds per state
        if state == "idle":
            interval = 2.0
        elif state == "thinking":
            interval = 0.6
        elif state == "typing":
            interval = 0.4
        else:
            interval = 0.5

        self._start_animation(state, interval)

    def _start_animation(self, state: str, interval: float = 2.0) -> None:
        if self._timer:
            self._timer.cancel()
        frames = self.FRAMES.get(state, [IDLE_FRAME_0])
        self._frame_index = 0
        self._current = frames[0] if frames else ""
        if frames:
            self.refresh()
        if len(frames) > 1:
            self._timer = self.set_interval(interval, self._next_frame)

    def _next_frame(self) -> None:
        frames = self.FRAMES.get(self._state, [IDLE_FRAME_0])
        if not frames:
            return
        self._frame_index = (self._frame_index + 1) % len(frames)
        self._current = frames[self._frame_index]
        self.refresh()

    def render(self):
        return self._current if hasattr(self, '_current') else ""
