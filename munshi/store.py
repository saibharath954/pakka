"""Today's WhatsApp inbox. Operational state only; nothing learned lives here."""

from __future__ import annotations

import json
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable

from .seed_data import LIVE_MESSAGES


class Inbox:
    def __init__(self, path: Path | None, clock: Callable[[], datetime]):
        self.path = path
        self.clock = clock
        self._lock = threading.Lock()
        self.xml: dict[str, str] = {}
        self.messages: list[dict] = []
        if path and path.exists():
            self.messages = json.loads(path.read_text())
        else:
            self.reset()

    def reset(self) -> None:
        start = datetime.combine(self.clock().date(), time(8, 40), tzinfo=self.clock().tzinfo)
        self.messages = [
            {"id": f"W{i + 1:02d}", "retailer_id": rid, "text": text,
             "received_at": (start + timedelta(minutes=17 * i)).isoformat(), "status": "new",
             "order_no": None, "total": None}
            for i, (rid, text) in enumerate(LIVE_MESSAGES)
        ]
        self._save()

    def _save(self) -> None:
        if self.path:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self.messages, indent=2))

    def all(self) -> list[dict]:
        return sorted(self.messages, key=lambda x: x["received_at"], reverse=True)

    def get(self, mid: str) -> dict | None:
        return next((x for x in self.messages if x["id"] == mid), None)

    def add(self, rid: str, text: str) -> dict:
        n = max((int(x["id"][1:]) for x in self.messages), default=0) + 1
        msg = {"id": f"W{n:02d}", "retailer_id": rid, "text": text, "received_at": self.clock().isoformat(),
               "status": "new", "order_no": None, "total": None}
        self.messages.append(msg)
        self._save()
        return msg

    def mark_posted(self, mid: str, order_no: str, total: float, xml: str | None = None) -> None:
        if xml:
            self.xml[order_no] = xml
        msg = self.get(mid)
        if msg:
            msg.update(status="posted", order_no=order_no, total=total)
            self._save()
