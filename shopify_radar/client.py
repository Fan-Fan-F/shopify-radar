"""Shopify HTTP client with timeout, retry, and JSON endpoint scraping."""

from __future__ import annotations
import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional, Tuple

from shopify_radar.models import Product, Collection, StoreSnapshot

logger = logging.getLogger("shopify_radar.client")

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
]


class ShopifyClientError(Exception):
    """Base exception for client errors."""
    pass


class StoreNotFoundError(ShopifyClientError):
    """Store or endpoint not found (404)."""
    pass


class RateLimitError(ShopifyClientError):
    """Rate limit encountered (429)."""
    pass


class ShopifyClient:
    """Robust client to query Shopify public JSON endpoints with timeout & retries."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        retries: int = 3,
        backoff_factor: float = 1.0,
        user_agent: Optional[str] = None,
    ):
        self.base_url = self._normalize_url(base_url)
        self.domain = urllib.parse.urlparse(self.base_url).netloc
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.user_agent = user_agent

    @staticmethod
    def _normalize_url(url: str) -> str:
        clean = url.strip()
        if not clean.startswith("http://") and not clean.startswith("https://"):
            clean = "https://" + clean
        parsed = urllib.parse.urlparse(clean)
        # Ensure scheme and netloc only
        netloc = parsed.netloc or parsed.path
        scheme = parsed.scheme or "https"
        return f"{scheme}://{netloc}".rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        ua = self.user_agent or random.choice(DEFAULT_USER_AGENTS)
        return {
            "User-Agent": ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _request_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform GET request with retry backoff and timeout."""
        query_string = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query_string}"

        last_error = None
        for attempt in range(1, self.retries + 1):
            req = urllib.request.Request(url, headers=self._get_headers())
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = resp.status
                    if status == 200:
                        body = resp.read().decode("utf-8")
                        try:
                            return json.loads(body)
                        except json.JSONDecodeError as exc:
                            raise ShopifyClientError(f"Failed to parse JSON response from {url}: {exc}") from exc
                    else:
                        raise ShopifyClientError(f"Unexpected status code {status} from {url}")

            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 404:
                    raise StoreNotFoundError(f"Endpoint not found: {url} (HTTP 404)") from exc
                elif exc.code == 429:
                    logger.warning(f"Rate limited by {self.domain} (429), attempt {attempt}/{self.retries}")
                    if attempt == self.retries:
                        raise RateLimitError(f"Rate limited by {self.domain} after {self.retries} attempts.") from exc
                else:
                    logger.warning(f"HTTP error {exc.code} for {url}, attempt {attempt}/{self.retries}")

            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning(f"Network error connecting to {url}: {exc.reason}, attempt {attempt}/{self.retries}")

            except Exception as exc:
                last_error = exc
                logger.warning(f"Unexpected error for {url}: {exc}, attempt {attempt}/{self.retries}")

            if attempt < self.retries:
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_time)

        raise ShopifyClientError(f"Request failed for {url} after {self.retries} attempts: {last_error}")

    def peek_product(self) -> Optional[Product]:
        """Fetch a single product for fast verification and connectivity check."""
        data = self._request_json("/products.json", {"limit": 1})
        products_raw = data.get("products", [])
        if not products_raw:
            return None
        return Product.from_dict(products_raw[0], base_url=self.base_url)

    def fetch_products(self, limit: Optional[int] = None, page_size: int = 250) -> List[Product]:
        """Fetch all or up to `limit` products from Shopify."""
        products: List[Product] = []
        page = 1
        page_size = min(page_size, 250)

        while True:
            params = {"page": page, "limit": page_size}
            data = self._request_json("/products.json", params)
            batch = data.get("products", [])
            if not batch:
                break

            for item in batch:
                prod = Product.from_dict(item, base_url=self.base_url)
                products.append(prod)
                if limit and len(products) >= limit:
                    return products[:limit]

            if len(batch) < page_size:
                break
            page += 1

        return products

    def fetch_collections(self, limit: Optional[int] = None, page_size: int = 250) -> List[Collection]:
        """Fetch all or up to `limit` collections from Shopify."""
        collections: List[Collection] = []
        page = 1
        page_size = min(page_size, 250)

        while True:
            try:
                params = {"page": page, "limit": page_size}
                data = self._request_json("/collections.json", params)
                batch = data.get("collections", [])
                if not batch:
                    break

                for item in batch:
                    coll = Collection.from_dict(item)
                    collections.append(coll)
                    if limit and len(collections) >= limit:
                        return collections[:limit]

                if len(batch) < page_size:
                    break
                page += 1
            except (ShopifyClientError, StoreNotFoundError):
                # /collections.json might not be public on all stores
                break

        return collections

    def fetch_snapshot(
        self,
        product_limit: Optional[int] = None,
        include_collections: bool = True,
    ) -> StoreSnapshot:
        """Fetch complete store data and return a StoreSnapshot object."""
        start_time = time.time()
        products = self.fetch_products(limit=product_limit)

        collections: List[Collection] = []
        if include_collections:
            collections = self.fetch_collections()

        elapsed = round(time.time() - start_time, 2)
        utc_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return StoreSnapshot(
            store_url=self.base_url,
            domain=self.domain,
            timestamp=utc_now,
            products_count=len(products),
            collections_count=len(collections),
            products=products,
            collections=collections,
            metadata={
                "fetch_duration_seconds": elapsed,
                "product_limit": product_limit,
            },
        )

    def download_image(self, url: str, output_path: str) -> bool:
        """Download a single image file with timeout."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": random.choice(DEFAULT_USER_AGENTS)})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(resp.read())
                    return True
        except Exception as exc:
            logger.warning(f"Failed to download image {url}: {exc}")
        return False
