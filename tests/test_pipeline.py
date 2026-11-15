"""End-to-end integration tests using local mock server fixtures."""

import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from shopify_radar.client import ShopifyClient
from shopify_radar.diff import calculate_diff
from shopify_radar.models import StoreSnapshot
from shopify_radar.reporter import DiffReporter
from shopify_radar.storage import SnapshotStorage


class MockShopifyHandler(http.server.BaseHTTPRequestHandler):
    products_file = "fixtures/v1_products.json"
    collections_file = "fixtures/collections.json"

    def log_message(self, format, *args):
        # Suppress logging to keep test output clean
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


class TestShopifyRadarPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start mock server on an ephemeral port
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), MockShopifyHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SnapshotStorage(base_dir=self.temp_dir)
        MockShopifyHandler.products_file = "fixtures/v1_products.json"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_peek_and_fetch_pipeline(self):
        client = ShopifyClient(base_url=self.base_url, timeout=5.0)

        # 1. Test peek
        sample = client.peek_product()
        self.assertIsNotNone(sample)
        self.assertEqual(sample.id, "1001")
        self.assertEqual(sample.handle, "ergonomic-office-chair")

        # 2. Test initial fetch & snapshot
        snap1 = client.fetch_snapshot()
        self.assertEqual(snap1.products_count, 3)
        self.assertEqual(snap1.collections_count, 1)

        saved_path1 = self.storage.save_snapshot(snap1)
        self.assertTrue(saved_path1.exists())

        loaded_snap1 = self.storage.load_snapshot(saved_path1)
        self.assertEqual(loaded_snap1.products_count, 3)

        # 3. Switch mock server to v2 products
        MockShopifyHandler.products_file = "fixtures/v2_products.json"

        snap2 = client.fetch_snapshot()
        self.assertEqual(snap2.products_count, 3)

        # Ensure different timestamp
        snap2.timestamp = "2026-11-15T12:00:00Z"
        saved_path2 = self.storage.save_snapshot(snap2)
        self.assertTrue(saved_path2.exists())

        # 4. Test diff calculation
        diff = calculate_diff(loaded_snap1, snap2)
        self.assertTrue(diff.has_changes)

        # Verifications
        # New: 1004 (Heavy Duty Monitor Arm)
        self.assertEqual(len(diff.new_products), 1)
        self.assertEqual(diff.new_products[0].id, "1004")
        self.assertEqual(diff.new_products[0].handle, "heavy-duty-monitor-arm")

        # Removed: 1002 (Bamboo Standing Desk)
        self.assertEqual(len(diff.removed_products), 1)
        self.assertEqual(diff.removed_products[0].id, "1002")

        # Modified: 1001 (Chair - price drop & title) & 1003 (Keyboard - availability)
        self.assertEqual(len(diff.modified_products), 2)

        mod_map = {m.product_id: m for m in diff.modified_products}
        chair_mod = mod_map["1001"]
        self.assertTrue(chair_mod.title_changed)
        self.assertEqual(len(chair_mod.price_changes), 2)
        pc_v1 = [pc for pc in chair_mod.price_changes if pc.variant_id == "2001"][0]
        self.assertEqual(pc_v1.old_price, 199.99)
        self.assertEqual(pc_v1.new_price, 169.99)
        self.assertEqual(pc_v1.diff, -30.0)

        kb_mod = mod_map["1003"]
        self.assertEqual(len(kb_mod.availability_changes), 1)
        self.assertFalse(kb_mod.availability_changes[0].new_available)

        # 5. Test reports
        reporter = DiffReporter(diff)
        term_text = reporter.render_terminal()
        self.assertIn("SHOPIFY RADAR — CHANGE DETECTION REPORT", term_text)
        self.assertIn("Heavy Duty Monitor Arm", term_text)
        self.assertIn("Bamboo Standing Desk", term_text)

        md_text = reporter.render_markdown()
        self.assertIn("# Shopify Radar — Store Change Report", md_text)
        self.assertIn("## New Products", md_text)
        self.assertIn("## Delisted Products", md_text)

        json_text = reporter.render_json()
        data = json.loads(json_text)
        self.assertTrue(data["has_changes"])
        self.assertEqual(data["summary"]["new_products_count"], 1)
        self.assertEqual(data["summary"]["removed_products_count"], 1)
        self.assertEqual(data["summary"]["modified_products_count"], 2)


if __name__ == "__main__":
    unittest.main()
