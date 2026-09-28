"""The CRM row for each lead: name, phone, segment, status.

This is deliberately *not* where knowledge lives. It holds the fields a
spreadsheet would hold. Everything learned from conversations (objections,
promises, family decision makers, what worked) goes to Hindsight.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .seed_data import LEADS

SEGMENT_LABELS = {
    "independent_house": "Independent house",
    "apartment": "Apartment",
    "commercial": "Commercial",
    "farm": "Farm",
}


class CRM:
    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        self.leads: dict[str, dict[str, Any]] = {}
        if path and path.exists():
            self.leads = json.loads(path.read_text())
        else:
            self.reset()

    def reset(self) -> None:
        self.leads = {}
        for lead in LEADS:
            row = asdict(lead)
            row.update(last_message=None, last_contact=None)
            self.leads[lead.id] = row
        self._save()

    def _save(self) -> None:
        if not self.path:
            return
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.leads, indent=2))

    def get(self, lead_id: str) -> dict[str, Any]:
        if lead_id not in self.leads:
            raise KeyError(lead_id)
        return self.leads[lead_id]

    def all(self) -> list[dict[str, Any]]:
        return sorted(self.leads.values(), key=lambda r: r["id"])

    def add(self, row: dict[str, Any]) -> dict[str, Any]:
        next_id = f"L{max(int(k[1:]) for k in self.leads) + 1:02d}" if self.leads else "L01"
        row = {"id": next_id, "status": "open", "language": "English", "monthly_bill_inr": None,
               "phone": "", "source": "Manual", "last_message": None, "last_contact": None, **row}
        row["id"] = next_id
        self.leads[next_id] = row
        self._save()
        return row

    def touch(self, lead_id: str, *, message: str | None = None, when: str | None = None,
              status: str | None = None) -> None:
        row = self.get(lead_id)
        if message is not None:
            row["last_message"] = message
        if when is not None:
            row["last_contact"] = when
        if status is not None:
            row["status"] = status
        self._save()


def lead_card(row: dict[str, Any]) -> str:
    bill = f"Rs {row['monthly_bill_inr']:,}/month" if row.get("monthly_bill_inr") else "unknown"
    return (
        f"Name: {row['name']} ({row['id']})\n"
        f"Segment: {SEGMENT_LABELS.get(row['segment'], row['segment'])}\n"
        f"Locality: {row['locality']}\n"
        f"Source: {row['source']}\n"
        f"Electricity bill: {bill}\n"
        f"Status: {row['status']}"
    )
