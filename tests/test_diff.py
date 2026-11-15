"""Unit tests for differential comparison engine."""

import unittest
from shopify_radar.models import Product, Variant, StoreSnapshot
from shopify_radar.diff import calculate_diff


class TestDiffEngine(unittest.TestCase):
    def setUp(self):
        self.p1 = Product(
            id="101",
            title="Sneakers Pro",
            handle="sneakers-pro",
            vendor="Nike",
            product_type="Shoes",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            tags=["shoes", "running"],
            variants=[
                Variant(id="v1", title="Size 9", price=100.0, available=True),
                Variant(id="v2", title="Size 10", price=100.0, available=True),
            ],
        )
        self.p2 = Product(
            id="102",
            title="Vintage Cap",
            handle="vintage-cap",
            vendor="Puma",
            product_type="Hats",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            tags=["hat", "vintage"],
            variants=[
                Variant(id="v3", title="One Size", price=25.0, available=True),
            ],
        )

        self.snap_old = StoreSnapshot(
            store_url="https://test-shop.myshopify.com",
            domain="test-shop.myshopify.com",
            timestamp="2026-11-15T10:00:00Z",
            products_count=2,
            collections_count=0,
            products=[self.p1, self.p2],
        )

    def test_new_product_and_removed_product(self):
        p3_new = Product(
            id="103",
            title="Smart Watch",
            handle="smart-watch",
            vendor="Apple",
            product_type="Electronics",
            created_at="2026-11-15T11:00:00Z",
            updated_at="2026-11-15T11:00:00Z",
            tags=["gadget"],
            variants=[Variant(id="v4", title="44mm", price=299.0, available=True)],
        )

        snap_new = StoreSnapshot(
            store_url="https://test-shop.myshopify.com",
            domain="test-shop.myshopify.com",
            timestamp="2026-11-15T12:00:00Z",
            products_count=2,
            collections_count=0,
            products=[self.p1, p3_new],  # p2 removed, p3 added
        )

        diff = calculate_diff(self.snap_old, snap_new)
        self.assertTrue(diff.has_changes)
        self.assertEqual(len(diff.new_products), 1)
        self.assertEqual(diff.new_products[0].id, "103")
        self.assertEqual(len(diff.removed_products), 1)
        self.assertEqual(diff.removed_products[0].id, "102")
        self.assertEqual(len(diff.modified_products), 0)

    def test_price_change_and_availability(self):
        p1_modified = Product(
            id="101",
            title="Sneakers Pro V2",  # title changed
            handle="sneakers-pro",
            vendor="Nike",
            product_type="Shoes",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-11-15T12:00:00Z",
            tags=["shoes", "running", "sale"],  # 'sale' added
            variants=[
                Variant(id="v1", title="Size 9", price=80.0, available=True),   # $100 -> $80 (-20%)
                Variant(id="v2", title="Size 10", price=100.0, available=False), # In stock -> Out of stock
            ],
        )

        snap_new = StoreSnapshot(
            store_url="https://test-shop.myshopify.com",
            domain="test-shop.myshopify.com",
            timestamp="2026-11-15T12:00:00Z",
            products_count=2,
            collections_count=0,
            products=[p1_modified, self.p2],
        )

        diff = calculate_diff(self.snap_old, snap_new)
        self.assertTrue(diff.has_changes)
        self.assertEqual(len(diff.modified_products), 1)

        mod = diff.modified_products[0]
        self.assertEqual(mod.product_id, "101")
        self.assertTrue(mod.title_changed)
        self.assertIn("sale", mod.tags_added)

        # Price check
        self.assertEqual(len(mod.price_changes), 1)
        pc = mod.price_changes[0]
        self.assertEqual(pc.variant_id, "v1")
        self.assertEqual(pc.old_price, 100.0)
        self.assertEqual(pc.new_price, 80.0)
        self.assertEqual(pc.diff, -20.0)
        self.assertEqual(pc.diff_pct, -20.0)

        # Availability check
        self.assertEqual(len(mod.availability_changes), 1)
        ac = mod.availability_changes[0]
        self.assertEqual(ac.variant_id, "v2")
        self.assertTrue(ac.old_available)
        self.assertFalse(ac.new_available)


if __name__ == "__main__":
    unittest.main()
