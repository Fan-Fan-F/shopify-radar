"""Continuous monitoring radar loop for Shopify stores."""

from __future__ import annotations
import logging
import time
from typing import Optional, Callable

from shopify_radar.client import ShopifyClient, ShopifyClientError
from shopify_radar.storage import SnapshotStorage
from shopify_radar.diff import calculate_diff
from shopify_radar.reporter import DiffReporter
from shopify_radar.models import SnapshotDiff

logger = logging.getLogger("shopify_radar.monitor")


class MonitorRadar:
    """Orchestrates periodic crawling, snapshotting, diffing, and reporting."""

    def __init__(
        self,
        client: ShopifyClient,
        storage: Optional[SnapshotStorage] = None,
        interval: int = 300,
        quiet_no_change: bool = False,
        export_markdown: Optional[str] = None,
        on_diff_callback: Optional[Callable[[SnapshotDiff], None]] = None,
    ):
        self.client = client
        self.storage = storage or SnapshotStorage()
        self.interval = interval
        self.quiet_no_change = quiet_no_change
        self.export_markdown = export_markdown
        self.on_diff_callback = on_diff_callback

    def run_once(self) -> Optional[SnapshotDiff]:
        """Perform a single round of fetch, snapshot, and diff."""
        domain = self.client.domain
        prior_snapshot = self.storage.get_latest_snapshot(domain)

        # 1. Fetch current snapshot
        current_snapshot = self.client.fetch_snapshot()

        # 2. Persist new snapshot
        snapshot_file = self.storage.save_snapshot(current_snapshot)
        logger.info(f"Saved snapshot to {snapshot_file}")

        # 3. Calculate diff if prior exists
        if not prior_snapshot:
            print(f"[*] Initial baseline snapshot created for {domain} ({current_snapshot.products_count} products).")
            return None

        diff = calculate_diff(prior_snapshot, current_snapshot)
        reporter = DiffReporter(diff)

        if diff.has_changes or not self.quiet_no_change:
            print(reporter.render_terminal())

        if self.export_markdown and diff.has_changes:
            with open(self.export_markdown, "w", encoding="utf-8") as f:
                f.write(reporter.render_markdown())
            print(f"[+] Markdown report saved to {self.export_markdown}")

        if self.on_diff_callback:
            self.on_diff_callback(diff)

        return diff

    def start_loop(self, max_runs: Optional[int] = None):
        """Start the continuous periodic monitoring loop."""
        print(f"[*] Starting Shopify Radar Monitor for {self.client.base_url}")
        print(f"[*] Poll interval: {self.interval}s. Press Ctrl+C to stop.")

        runs = 0
        try:
            while True:
                runs += 1
                start_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print(f"\n--- [Round {runs}] Checking {self.client.domain} at {start_ts} ---")

                try:
                    self.run_once()
                except ShopifyClientError as exc:
                    logger.error(f"Error checking {self.client.domain}: {exc}")
                    print(f"[!] Warning: Scrape error: {exc}")
                except Exception as exc:
                    logger.exception(f"Unexpected failure: {exc}")
                    print(f"[!] Critical error during round: {exc}")

                if max_runs and runs >= max_runs:
                    print(f"[*] Completed {runs} rounds. Exiting monitor.")
                    break

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n[*] Monitor stopped by user.")
