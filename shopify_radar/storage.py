"""Snapshot persistence and storage manager."""

from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from shopify_radar.models import StoreSnapshot


class SnapshotStorage:
    """Manages saving, loading, and listing JSON snapshots."""

    def __init__(self, base_dir: str = "snapshots"):
        self.base_dir = Path(base_dir)

    def _sanitize_name(self, name: str) -> str:
        return re.sub(r"[^\w\-.]", "_", name)

    def get_store_dir(self, domain: str) -> Path:
        safe_domain = self._sanitize_name(domain)
        store_dir = self.base_dir / safe_domain
        store_dir.mkdir(parents=True, exist_ok=True)
        return store_dir

    def save_snapshot(self, snapshot: StoreSnapshot) -> Path:
        """Save snapshot as JSON file."""
        store_dir = self.get_store_dir(snapshot.domain)
        # Format timestamp for safe filename: 2026-11-15T14-30-00Z
        safe_ts = snapshot.timestamp.replace(":", "-")
        filepath = store_dir / f"snapshot_{safe_ts}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    def load_snapshot(self, filepath: str | Path) -> StoreSnapshot:
        """Load snapshot from given JSON path."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return StoreSnapshot.from_dict(data)

    def list_snapshots(self, domain: Optional[str] = None) -> List[Path]:
        """List snapshot paths ordered chronologically."""
        if not self.base_dir.exists():
            return []

        if domain:
            store_dir = self.base_dir / self._sanitize_name(domain)
            if not store_dir.exists():
                return []
            files = list(store_dir.glob("snapshot_*.json"))
        else:
            files = list(self.base_dir.glob("*/snapshot_*.json"))

        files.sort(key=lambda p: p.name)
        return files

    def get_latest_snapshot(self, domain: str) -> Optional[StoreSnapshot]:
        """Get the most recent snapshot for a domain."""
        files = self.list_snapshots(domain)
        if not files:
            return None
        return self.load_snapshot(files[-1])

    def get_latest_two_snapshots(self, domain: str) -> Tuple[Optional[StoreSnapshot], Optional[StoreSnapshot]]:
        """Get the previous snapshot and the latest snapshot for comparison."""
        files = self.list_snapshots(domain)
        if len(files) < 2:
            return (None, self.load_snapshot(files[-1]) if files else None)
        return (self.load_snapshot(files[-2]), self.load_snapshot(files[-1]))
