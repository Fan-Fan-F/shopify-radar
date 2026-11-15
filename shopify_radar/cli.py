"""Command Line Interface for shopify-radar."""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from shopify_radar import __version__
from shopify_radar.client import ShopifyClient, ShopifyClientError
from shopify_radar.storage import SnapshotStorage
from shopify_radar.diff import calculate_diff
from shopify_radar.reporter import DiffReporter
from shopify_radar.monitor import MonitorRadar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shopify-radar",
        description="Shopify Radar — Product and price change detection & monitoring radar",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"shopify-radar {__version__}"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Subcommand: fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch store products and save a new snapshot")
    fetch_parser.add_argument("url", help="Store URL (e.g. https://store.myshopify.com)")
    fetch_parser.add_argument("-n", "--limit", type=int, default=None, help="Max products to fetch")
    fetch_parser.add_argument("--snapshots-dir", default="snapshots", help="Directory to save snapshots")
    fetch_parser.add_argument("--no-collections", action="store_true", help="Skip fetching collections")
    fetch_parser.add_argument("--download-images", default=None, help="Directory to download images to")
    fetch_parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")
    fetch_parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")

    # Subcommand: diff
    diff_parser = subparsers.add_parser("diff", help="Compare two snapshots or latest two snapshots of a store")
    diff_parser.add_argument("target", help="Store URL/domain OR path to old snapshot JSON")
    diff_parser.add_argument("new_snapshot", nargs="?", default=None, help="Path to new snapshot JSON (optional)")
    diff_parser.add_argument("-f", "--format", choices=["terminal", "markdown", "json"], default="terminal", help="Output format")
    diff_parser.add_argument("-o", "--output", default=None, help="Path to save output report file")
    diff_parser.add_argument("--snapshots-dir", default="snapshots", help="Snapshots directory")

    # Subcommand: snapshots
    snap_parser = subparsers.add_parser("snapshots", help="List stored snapshots")
    snap_parser.add_argument("domain", nargs="?", default=None, help="Optional store domain to filter by")
    snap_parser.add_argument("--snapshots-dir", default="snapshots", help="Snapshots directory")

    # Subcommand: monitor
    monitor_parser = subparsers.add_parser("monitor", help="Periodically monitor store and detect changes")
    monitor_parser.add_argument("url", help="Store URL to monitor")
    monitor_parser.add_argument("-i", "--interval", type=int, default=300, help="Poll interval in seconds (default 300)")
    monitor_parser.add_argument("--max-runs", type=int, default=None, help="Max monitoring rounds (default: infinite)")
    monitor_parser.add_argument("-q", "--quiet-no-change", action="store_true", help="Only output when changes occur")
    monitor_parser.add_argument("--export-md", default=None, help="Save markdown report to path when changes occur")
    monitor_parser.add_argument("--snapshots-dir", default="snapshots", help="Snapshots directory")
    monitor_parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")
    monitor_parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")

    # Subcommand: peek
    peek_parser = subparsers.add_parser("peek", help="Quick peek at a store to verify connectivity")
    peek_parser.add_argument("url", help="Store URL to peek")
    peek_parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")

    return parser


def handle_fetch(args) -> int:
    client = ShopifyClient(
        base_url=args.url,
        timeout=args.timeout,
        retries=args.retries,
    )
    storage = SnapshotStorage(base_dir=args.snapshots_dir)

    print(f"[*] Fetching products from {client.base_url}...")
    try:
        snapshot = client.fetch_snapshot(
            product_limit=args.limit,
            include_collections=not args.no_collections,
        )
    except ShopifyClientError as exc:
        print(f"[!] Error fetching store: {exc}", file=sys.stderr)
        return 1

    path = storage.save_snapshot(snapshot)
    print(f"[+] Successfully saved snapshot: {path}")
    print(f"    - Domain: {snapshot.domain}")
    print(f"    - Products: {snapshot.products_count}")
    print(f"    - Collections: {snapshot.collections_count}")
    print(f"    - Timestamp: {snapshot.timestamp}")

    if args.download_images:
        images_dir = Path(args.download_images)
        print(f"[*] Downloading images to {images_dir}...")
        downloaded = 0
        for p in snapshot.products:
            for idx, img_url in enumerate(p.images):
                ext = img_url.split("?")[0].split(".")[-1]
                if ext not in ["jpg", "jpeg", "png", "webp"]:
                    ext = "jpg"
                filename = f"{p.handle}_{idx}.{ext}"
                dest = images_dir / filename
                if client.download_image(img_url, str(dest)):
                    downloaded += 1
        print(f"[+] Downloaded {downloaded} images.")

    return 0


def handle_diff(args) -> int:
    storage = SnapshotStorage(base_dir=args.snapshots_dir)

    if args.new_snapshot is not None:
        # User specified two snapshot file paths
        old_path = Path(args.target)
        new_path = Path(args.new_snapshot)
        if not old_path.exists():
            print(f"[!] File not found: {old_path}", file=sys.stderr)
            return 1
        if not new_path.exists():
            print(f"[!] File not found: {new_path}", file=sys.stderr)
            return 1
        old_snap = storage.load_snapshot(old_path)
        new_snap = storage.load_snapshot(new_path)
    else:
        # User specified a store domain or URL; compare latest two
        domain = ShopifyClient._normalize_url(args.target)
        domain = domain.replace("https://", "").replace("http://", "")
        old_snap, new_snap = storage.get_latest_two_snapshots(domain)

        if new_snap is None:
            print(f"[!] No snapshots found for store '{domain}' in {args.snapshots_dir}.", file=sys.stderr)
            return 1
        if old_snap is None:
            print(f"[!] Only 1 snapshot found for '{domain}'. At least 2 snapshots are needed to diff.", file=sys.stderr)
            return 1

    diff = calculate_diff(old_snap, new_snap)
    reporter = DiffReporter(diff)

    if args.format == "json":
        output_text = reporter.render_json()
    elif args.format == "markdown":
        output_text = reporter.render_markdown()
    else:
        output_text = reporter.render_terminal()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"[+] Report saved to {args.output}")
    else:
        print(output_text)

    return 0


def handle_snapshots(args) -> int:
    storage = SnapshotStorage(base_dir=args.snapshots_dir)
    domain = None
    if args.domain:
        domain = ShopifyClient._normalize_url(args.domain).replace("https://", "").replace("http://", "")

    snapshots = storage.list_snapshots(domain)
    if not snapshots:
        print("No snapshots found.")
        return 0

    print(f"Found {len(snapshots)} snapshot(s):")
    for s in snapshots:
        print(f"  - {s}")
    return 0


def handle_monitor(args) -> int:
    client = ShopifyClient(
        base_url=args.url,
        timeout=args.timeout,
        retries=args.retries,
    )
    storage = SnapshotStorage(base_dir=args.snapshots_dir)
    monitor = MonitorRadar(
        client=client,
        storage=storage,
        interval=args.interval,
        quiet_no_change=args.quiet_no_change,
        export_markdown=args.export_md,
    )
    monitor.start_loop(max_runs=args.max_runs)
    return 0


def handle_peek(args) -> int:
    client = ShopifyClient(
        base_url=args.url,
        timeout=args.timeout,
        retries=1,
    )
    print(f"[*] Peeking into {client.base_url}...")
    try:
        product = client.peek_product()
        if not product:
            print("[!] Store responded with 0 products.")
            return 1

        print("[+] Store is reachable! Sample product:")
        print(f"    ID: {product.id}")
        print(f"    Title: {product.title}")
        print(f"    Handle: {product.handle}")
        print(f"    Vendor: {product.vendor}")
        print(f"    Product Type: {product.product_type}")
        print(f"    Variants: {len(product.variants)}")
        if product.variants:
            v0 = product.variants[0]
            print(f"    First Variant: '{v0.title}' - ${v0.price:.2f} (Available: {v0.available})")
        print(f"    Images Count: {len(product.images)}")
        return 0
    except ShopifyClientError as exc:
        print(f"[!] Peek failed: {exc}", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "fetch":
        return handle_fetch(args)
    elif args.subcommand == "diff":
        return handle_diff(args)
    elif args.subcommand == "snapshots":
        return handle_snapshots(args)
    elif args.subcommand == "monitor":
        return handle_monitor(args)
    elif args.subcommand == "peek":
        return handle_peek(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
