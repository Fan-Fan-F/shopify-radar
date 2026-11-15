"""Differential comparison engine between store snapshots."""

from __future__ import annotations
from typing import Dict, List

from shopify_radar.models import (
    StoreSnapshot,
    SnapshotDiff,
    Product,
    ProductChange,
    PriceChange,
    AvailabilityChange,
    Variant,
)


def calculate_diff(old_snapshot: StoreSnapshot, new_snapshot: StoreSnapshot) -> SnapshotDiff:
    """Compare two store snapshots and compute differences."""
    old_prod_map: Dict[str, Product] = {p.id: p for p in old_snapshot.products}
    new_prod_map: Dict[str, Product] = {p.id: p for p in new_snapshot.products}

    # Also map by handle as fallback if IDs differ
    old_handle_map: Dict[str, Product] = {p.handle: p for p in old_snapshot.products if p.handle}
    new_handle_map: Dict[str, Product] = {p.handle: p for p in new_snapshot.products if p.handle}

    new_products: List[Product] = []
    removed_products: List[Product] = []
    modified_products: List[ProductChange] = []

    # Detect new products
    for pid, new_p in new_prod_map.items():
        if pid not in old_prod_map and new_p.handle not in old_handle_map:
            new_products.append(new_p)

    # Detect removed products
    for pid, old_p in old_prod_map.items():
        if pid not in new_prod_map and old_p.handle not in new_handle_map:
            removed_products.append(old_p)

    # Detect modifications in existing products
    for pid, new_p in new_prod_map.items():
        old_p = old_prod_map.get(pid)
        if not old_p and new_p.handle in old_handle_map:
            old_p = old_handle_map[new_p.handle]

        if not old_p:
            continue

        # Check title change
        title_changed = old_p.title != new_p.title
        old_title = old_p.title if title_changed else None
        new_title = new_p.title if title_changed else None

        # Check tag changes
        old_tags_set = set(old_p.tags)
        new_tags_set = set(new_p.tags)
        tags_added = sorted(list(new_tags_set - old_tags_set))
        tags_removed = sorted(list(old_tags_set - new_tags_set))

        # Check variant price and availability changes
        old_var_map: Dict[str, Variant] = {v.id: v for v in old_p.variants}
        new_var_map: Dict[str, Variant] = {v.id: v for v in new_p.variants}

        price_changes: List[PriceChange] = []
        availability_changes: List[AvailabilityChange] = []

        for vid, new_v in new_var_map.items():
            old_v = old_var_map.get(vid)
            if not old_v:
                # Check match by variant title / position
                for candidate in old_var_map.values():
                    if candidate.title == new_v.title and candidate.title != "Default Title":
                        old_v = candidate
                        break

            if old_v:
                # Compare price
                if round(old_v.price, 2) != round(new_v.price, 2) or old_v.compare_at_price != new_v.compare_at_price:
                    price_changes.append(
                        PriceChange(
                            variant_id=new_v.id,
                            variant_title=new_v.title,
                            old_price=old_v.price,
                            new_price=new_v.price,
                            old_compare_at=old_v.compare_at_price,
                            new_compare_at=new_v.compare_at_price,
                        )
                    )

                # Compare availability
                if old_v.available != new_v.available:
                    availability_changes.append(
                        AvailabilityChange(
                            variant_id=new_v.id,
                            variant_title=new_v.title,
                            old_available=old_v.available,
                            new_available=new_v.available,
                        )
                    )

        if title_changed or tags_added or tags_removed or price_changes or availability_changes:
            modified_products.append(
                ProductChange(
                    product_id=new_p.id,
                    title=new_p.title,
                    handle=new_p.handle,
                    url=new_p.url or old_p.url,
                    title_changed=title_changed,
                    old_title=old_title,
                    new_title=new_title,
                    tags_added=tags_added,
                    tags_removed=tags_removed,
                    price_changes=price_changes,
                    availability_changes=availability_changes,
                )
            )

    return SnapshotDiff(
        store_url=new_snapshot.store_url,
        domain=new_snapshot.domain,
        old_timestamp=old_snapshot.timestamp,
        new_timestamp=new_snapshot.timestamp,
        new_products=new_products,
        removed_products=removed_products,
        modified_products=modified_products,
    )
