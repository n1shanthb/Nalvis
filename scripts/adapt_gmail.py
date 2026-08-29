"""Adapt legacy gmail.py for portable_core (drop aip.gmail.store)."""

from pathlib import Path

SRC = Path(r"e:\agentsuite\legacy_harvest\src\aip\tools\gmail.py")
DST = Path(r"e:\agentsuite\portable_core\src\aip\tools\gmail.py")

text = SRC.read_text(encoding="utf-8")
text = text.replace(
    "from aip.gmail.store import GmailWatchStore\n",
    "",
)
text = text.replace(
    "_watch_store = GmailWatchStore()\n",
    """
# In-memory watch state (portable; no DB store)
_WATCH_STATE: dict = {}


class _InMemoryWatchStore:
    def get(self) -> dict:
        return dict(_WATCH_STATE)

    def upsert(self, **kwargs) -> dict:
        _WATCH_STATE.update({k: v for k, v in kwargs.items() if v is not None})
        return dict(_WATCH_STATE)


_watch_store = _InMemoryWatchStore()
""",
)
DST.write_text(text, encoding="utf-8")
print("wrote", DST, "bytes", DST.stat().st_size)
