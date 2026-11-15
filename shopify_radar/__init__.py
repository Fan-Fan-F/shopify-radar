"""Shopify Radar — Product and price change detection & monitoring radar."""

__version__ = "0.1.0"

from shopify_radar.models import (
    Product,
    Variant,
    Collection,
    StoreSnapshot,
    SnapshotDiff,
    PriceChange,
    ProductChange,
)
from shopify_radar.client import ShopifyClient, ShopifyClientError
from shopify_radar.storage import SnapshotStorage
from shopify_radar.diff import calculate_diff
from shopify_radar.reporter import DiffReporter
from shopify_radar.monitor import MonitorRadar

__all__ = [
    "__version__",
    "Product",
    "Variant",
    "Collection",
    "StoreSnapshot",
    "SnapshotDiff",
    "PriceChange",
    "ProductChange",
    "ShopifyClient",
    "ShopifyClientError",
    "SnapshotStorage",
    "calculate_diff",
    "DiffReporter",
    "MonitorRadar",
]
