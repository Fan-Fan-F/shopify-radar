"""Human-readable terminal and Markdown reports for snapshot diffs."""

from __future__ import annotations
import json
from typing import Optional

from shopify_radar.models import SnapshotDiff


class DiffReporter:
    """Renders change reports into terminal text, Markdown, or JSON."""

    def __init__(self, diff: SnapshotDiff):
        self.diff = diff

    def render_terminal(self) -> str:
        """Render a clean, human-readable terminal report."""
        lines = []
        border = "=" * 64
        lines.append(border)
        lines.append(f"  SHOPIFY RADAR — CHANGE DETECTION REPORT")
        lines.append(border)
        lines.append(f"  Target Store : {self.diff.store_url or self.diff.domain}")
        lines.append(f"  Prior Snapshot: {self.diff.old_timestamp}")
        lines.append(f"  Latest Snapshot: {self.diff.new_timestamp}")
        lines.append(border)

        if not self.diff.has_changes:
            lines.append("  [INFO] No product or price changes detected between snapshots.")
            lines.append(border)
            return "\n".join(lines)

        lines.append("  SUMMARY OF CHANGES:")
        lines.append(f"    * New Products Added     : {len(self.diff.new_products)}")
        lines.append(f"    * Delisted / Removed     : {len(self.diff.removed_products)}")
        lines.append(f"    * Modified Products      : {len(self.diff.modified_products)}")
        lines.append("-" * 64)

        # 1. New Products
        if self.diff.new_products:
            lines.append(f"\n[+] NEW PRODUCTS ({len(self.diff.new_products)}):")
            for idx, p in enumerate(self.diff.new_products, 1):
                prices = [v.price for v in p.variants if v.price > 0]
                price_str = f"${min(prices):.2f}" if prices else "N/A"
                if prices and min(prices) != max(prices):
                    price_str = f"${min(prices):.2f} - ${max(prices):.2f}"
                vendor_str = f" [{p.vendor}]" if p.vendor else ""
                lines.append(f"  {idx}. {p.title}{vendor_str}")
                lines.append(f"     Price: {price_str} | Handle: {p.handle}")
                if p.tags:
                    lines.append(f"     Tags: {', '.join(p.tags[:5])}")
                if p.url:
                    lines.append(f"     URL: {p.url}")

        # 2. Removed Products
        if self.diff.removed_products:
            lines.append(f"\n[-] DELISTED / REMOVED PRODUCTS ({len(self.diff.removed_products)}):")
            for idx, p in enumerate(self.diff.removed_products, 1):
                lines.append(f"  {idx}. {p.title} (Handle: {p.handle}, ID: {p.id})")

        # 3. Modified Products
        if self.diff.modified_products:
            lines.append(f"\n[*] PRODUCT MODIFICATIONS & PRICE UPDATES ({len(self.diff.modified_products)}):")
            for idx, m in enumerate(self.diff.modified_products, 1):
                lines.append(f"  {idx}. {m.title} (Handle: {m.handle})")
                if m.title_changed:
                    lines.append(f"     [Title Changed] Old: '{m.old_title}' -> New: '{m.new_title}'")
                if m.tags_added:
                    lines.append(f"     [Tags Added] + {', '.join(m.tags_added)}")
                if m.tags_removed:
                    lines.append(f"     [Tags Removed] - {', '.join(m.tags_removed)}")

                for pc in m.price_changes:
                    sign = "+" if pc.diff > 0 else ""
                    arrow = "UP" if pc.diff > 0 else "DOWN"
                    lines.append(
                        f"     [Price {arrow}] Variant '{pc.variant_title}': "
                        f"${pc.old_price:.2f} -> ${pc.new_price:.2f} "
                        f"({sign}${pc.diff:.2f}, {sign}{pc.diff_pct:.1f}%)"
                    )

                for ac in m.availability_changes:
                    status_from = "In Stock" if ac.old_available else "Out of Stock"
                    status_to = "In Stock" if ac.new_available else "Out of Stock"
                    lines.append(f"     [Stock] Variant '{ac.variant_title}': {status_from} -> {status_to}")

        lines.append("\n" + border)
        return "\n".join(lines)

    def render_markdown(self) -> str:
        """Render a clean Markdown report for sharing or exporting."""
        lines = []
        lines.append(f"# Shopify Radar — Store Change Report")
        lines.append(f"")
        lines.append(f"- **Target Store**: `{self.diff.store_url or self.diff.domain}`")
        lines.append(f"- **Prior Snapshot**: `{self.diff.old_timestamp}`")
        lines.append(f"- **Latest Snapshot**: `{self.diff.new_timestamp}`")
        lines.append(f"")

        if not self.diff.has_changes:
            lines.append("> **Status**: No changes detected between snapshots.")
            return "\n".join(lines)

        lines.append(f"## Summary")
        lines.append(f"| Metric | Count |")
        lines.append(f"|---|---|")
        lines.append(f"| **New Products Added** | {len(self.diff.new_products)} |")
        lines.append(f"| **Delisted / Removed** | {len(self.diff.removed_products)} |")
        lines.append(f"| **Modified Products** | {len(self.diff.modified_products)} |")
        lines.append(f"")

        if self.diff.new_products:
            lines.append(f"## New Products ({len(self.diff.new_products)})")
            lines.append(f"| Title | Vendor | Price | Handle |")
            lines.append(f"|---|---|---|---|")
            for p in self.diff.new_products:
                prices = [v.price for v in p.variants if v.price > 0]
                price_str = f"${min(prices):.2f}" if prices else "N/A"
                if prices and min(prices) != max(prices):
                    price_str = f"${min(prices):.2f} - ${max(prices):.2f}"
                title_link = f"[{p.title}]({p.url})" if p.url else p.title
                lines.append(f"| {title_link} | {p.vendor or '-'} | {price_str} | `{p.handle}` |")
            lines.append(f"")

        if self.diff.removed_products:
            lines.append(f"## Delisted Products ({len(self.diff.removed_products)})")
            lines.append(f"| Title | Handle | ID |")
            lines.append(f"|---|---|---|")
            for p in self.diff.removed_products:
                lines.append(f"| {p.title} | `{p.handle}` | `{p.id}` |")
            lines.append(f"")

        if self.diff.modified_products:
            lines.append(f"## Product Updates ({len(self.diff.modified_products)})")
            for m in self.diff.modified_products:
                lines.append(f"### {m.title}")
                if m.url:
                    lines.append(f"- **Link**: {m.url}")
                if m.title_changed:
                    lines.append(f"- **Title**: ~~{m.old_title}~~ -> **{m.new_title}**")
                if m.price_changes:
                    lines.append(f"- **Price Adjustments**:")
                    for pc in m.price_changes:
                        sign = "+" if pc.diff > 0 else ""
                        lines.append(f"  - `{pc.variant_title}`: `${pc.old_price:.2f}` -> **`${pc.new_price:.2f}`** ({sign}${pc.diff:.2f}, {sign}{pc.diff_pct:.1f}%)")
                if m.availability_changes:
                    lines.append(f"- **Availability Shifts**:")
                    for ac in m.availability_changes:
                        from_s = "In Stock" if ac.old_available else "Out of Stock"
                        to_s = "In Stock" if ac.new_available else "Out of Stock"
                        lines.append(f"  - `{ac.variant_title}`: {from_s} -> **{to_s}**")
                if m.tags_added:
                    lines.append(f"- **Tags Added**: `{', '.join(m.tags_added)}`")
                if m.tags_removed:
                    lines.append(f"- **Tags Removed**: `{', '.join(m.tags_removed)}`")
                lines.append(f"")

        return "\n".join(lines)

    def render_json(self, indent: int = 2) -> str:
        """Render JSON format."""
        return json.dumps(self.diff.to_dict(), ensure_ascii=False, indent=indent)
