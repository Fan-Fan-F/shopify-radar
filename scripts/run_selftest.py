#!/usr/bin/env python3
"""Run complete end-to-end self-test for shopify-radar without external network."""

import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

PORT = 8989
SNAPSHOTS_DIR = "test_snapshots"


class MockShopifyHandler(http.server.BaseHTTPRequestHandler):
    products_file = "fixtures/v1_products.json"
    collections_file = "fixtures/collections.json"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed_path = self.path.split("?")[0]
        if parsed_path == "/products.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            with open(self.products_file, "rb") as f:
                self.wfile.write(f.read())
        elif parsed_path == "/collections.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            with open(self.collections_file, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()


def run_cmd(cmd):
    print(f"\n$ {' '.join(cmd)}")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print("[stderr]", res.stderr.strip())
    if res.returncode != 0:
        raise RuntimeError(f"Command failed with code {res.returncode}")
    return res.stdout


def main():
    if os.path.exists(SNAPSHOTS_DIR):
        shutil.rmtree(SNAPSHOTS_DIR)

    server = http.server.HTTPServer(("127.0.0.1", PORT), MockShopifyHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"[*] Mock Shopify server listening on http://127.0.0.1:{PORT}")

    try:
        # Step 1: Peek
        print("\n--- TEST 1: PEEK ---")
        run_cmd([sys.executable, "-m", "shopify_radar", "peek", f"http://127.0.0.1:{PORT}"])

        # Step 2: Fetch Snapshot 1 (v1)
        print("\n--- TEST 2: FETCH (V1) ---")
        MockShopifyHandler.products_file = "fixtures/v1_products.json"
        run_cmd([
            sys.executable, "-m", "shopify_radar", "fetch",
            f"http://127.0.0.1:{PORT}",
            "--snapshots-dir", SNAPSHOTS_DIR
        ])

        # Step 3: List Snapshots
        print("\n--- TEST 3: SNAPSHOTS LIST ---")
        run_cmd([
            sys.executable, "-m", "shopify_radar", "snapshots",
            "--snapshots-dir", SNAPSHOTS_DIR
        ])

        # Step 4: Switch to v2 and Fetch Snapshot 2
        print("\n--- TEST 4: FETCH (V2) ---")
        MockShopifyHandler.products_file = "fixtures/v2_products.json"
        time.sleep(1.2)  # Ensure unique second timestamp
        run_cmd([
            sys.executable, "-m", "shopify_radar", "fetch",
            f"http://127.0.0.1:{PORT}",
            "--snapshots-dir", SNAPSHOTS_DIR
        ])

        # Step 5: Diff terminal report
        print("\n--- TEST 5: DIFF TERMINAL REPORT ---")
        diff_out = run_cmd([
            sys.executable, "-m", "shopify_radar", "diff",
            f"127.0.0.1:{PORT}",
            "--snapshots-dir", SNAPSHOTS_DIR,
            "-f", "terminal"
        ])
        assert "SHOPIFY RADAR — CHANGE DETECTION REPORT" in diff_out
        assert "Heavy Duty Monitor Arm" in diff_out
        assert "Bamboo Standing Desk" in diff_out
        assert "Ergonomic Office Chair" in diff_out

        # Step 6: Diff Markdown report export
        print("\n--- TEST 6: DIFF MARKDOWN EXPORT ---")
        md_file = os.path.join(SNAPSHOTS_DIR, "report.md")
        run_cmd([
            sys.executable, "-m", "shopify_radar", "diff",
            f"127.0.0.1:{PORT}",
            "--snapshots-dir", SNAPSHOTS_DIR,
            "-f", "markdown",
            "-o", md_file
        ])
        assert os.path.exists(md_file)
        with open(md_file, "r") as f:
            md_content = f.read()
            assert "# Shopify Radar — Store Change Report" in md_content

        # Step 7: Diff JSON report export
        print("\n--- TEST 7: DIFF JSON EXPORT ---")
        json_file = os.path.join(SNAPSHOTS_DIR, "report.json")
        run_cmd([
            sys.executable, "-m", "shopify_radar", "diff",
            f"127.0.0.1:{PORT}",
            "--snapshots-dir", SNAPSHOTS_DIR,
            "-f", "json",
            "-o", json_file
        ])
        with open(json_file, "r") as f:
            diff_data = json.load(f)
            assert diff_data["has_changes"] is True
            assert diff_data["summary"]["new_products_count"] == 1
            assert diff_data["summary"]["removed_products_count"] == 1
            assert diff_data["summary"]["modified_products_count"] == 2

        # Step 8: Monitor command with max-runs 2
        print("\n--- TEST 8: MONITOR LOOP (2 ROUNDS) ---")
        run_cmd([
            sys.executable, "-m", "shopify_radar", "monitor",
            f"http://127.0.0.1:{PORT}",
            "--interval", "1",
            "--max-runs", "2",
            "--snapshots-dir", SNAPSHOTS_DIR,
            "-q"
        ])

        print("\n==========================================")
        print("ALL SELF-TESTS PASSED SUCCESSFULLY (8/8)!")
        print("==========================================")

    finally:
        server.shutdown()
        server.server_close()
        if os.path.exists(SNAPSHOTS_DIR):
            shutil.rmtree(SNAPSHOTS_DIR)


if __name__ == "__main__":
    main()
