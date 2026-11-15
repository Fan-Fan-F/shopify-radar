"""Data models for shopify-radar."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Variant:
    id: str
    title: str
    price: float
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    available: bool = True
    position: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Variant:
        price_raw = data.get("price")
        price = 0.0
        if price_raw is not None:
            try:
                price = float(price_raw)
            except (ValueError, TypeError):
                price = 0.0

        compare_raw = data.get("compare_at_price")
        compare_at_price = None
        if compare_raw is not None:
            try:
                compare_at_price = float(compare_raw)
            except (ValueError, TypeError):
                compare_at_price = None

        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "Default Title")),
            price=price,
            compare_at_price=compare_at_price,
            sku=str(data.get("sku", "")) if data.get("sku") else None,
            available=bool(data.get("available", True)),
            position=int(data.get("position", 1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Product:
    id: str
    title: str
    handle: str
    vendor: str
    product_type: str
    created_at: str
    updated_at: str
    published_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    variants: List[Variant] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_url: str = "") -> Product:
        raw_tags = data.get("tags", [])
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            tags = []

        raw_variants = data.get("variants", [])
        variants = [Variant.from_dict(v) for v in raw_variants if isinstance(v, dict)]

        raw_images = data.get("images", [])
        images: List[str] = []
        for img in raw_images:
            if isinstance(img, dict) and "src" in img:
                images.append(str(img["src"]))
            elif isinstance(img, str):
                images.append(img)

        handle = str(data.get("handle", ""))
        url = None
        if base_url and handle:
            clean_base = base_url.rstrip("/")
            url = f"{clean_base}/products/{handle}"

        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "Untitled Product")),
            handle=handle,
            vendor=str(data.get("vendor", "")),
            product_type=str(data.get("product_type", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            published_at=data.get("published_at"),
            tags=tags,
            variants=variants,
            images=images,
            url=url,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["variants"] = [v.to_dict() for v in self.variants]
        return d


@dataclass
class Collection:
    id: str
    handle: str
    title: str
    updated_at: str = ""
    body_html: Optional[str] = None
    products_count: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Collection:
        return cls(
            id=str(data.get("id", "")),
            handle=str(data.get("handle", "")),
            title=str(data.get("title", "")),
            updated_at=str(data.get("updated_at", "")),
            body_html=data.get("body_html"),
            products_count=data.get("products_count"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StoreSnapshot:
    store_url: str
    domain: str
    timestamp: str
    products_count: int
    collections_count: int
    products: List[Product] = field(default_factory=list)
    collections: List[Collection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_url": self.store_url,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "products_count": self.products_count,
            "collections_count": self.collections_count,
            "metadata": self.metadata,
            "products": [p.to_dict() for p in self.products],
            "collections": [c.to_dict() for c in self.collections],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StoreSnapshot:
        base_url = data.get("store_url", "")
        products = [
            Product.from_dict(p, base_url=base_url)
            for p in data.get("products", [])
            if isinstance(p, dict)
        ]
        collections = [
            Collection.from_dict(c)
            for c in data.get("collections", [])
            if isinstance(c, dict)
        ]
        return cls(
            store_url=base_url,
            domain=str(data.get("domain", "")),
            timestamp=str(data.get("timestamp", "")),
            products_count=int(data.get("products_count", len(products))),
            collections_count=int(data.get("collections_count", len(collections))),
            products=products,
            collections=collections,
            metadata=data.get("metadata", {}),
        )


@dataclass
class PriceChange:
    variant_id: str
    variant_title: str
    old_price: float
    new_price: float
    old_compare_at: Optional[float] = None
    new_compare_at: Optional[float] = None

    @property
    def diff(self) -> float:
        return round(self.new_price - self.old_price, 2)

    @property
    def diff_pct(self) -> float:
        if self.old_price <= 0:
            return 0.0
        return round(((self.new_price - self.old_price) / self.old_price) * 100, 2)


@dataclass
class AvailabilityChange:
    variant_id: str
    variant_title: str
    old_available: bool
    new_available: bool


@dataclass
class ProductChange:
    product_id: str
    title: str
    handle: str
    url: Optional[str] = None
    title_changed: bool = False
    old_title: Optional[str] = None
    new_title: Optional[str] = None
    tags_added: List[str] = field(default_factory=list)
    tags_removed: List[str] = field(default_factory=list)
    price_changes: List[PriceChange] = field(default_factory=list)
    availability_changes: List[AvailabilityChange] = field(default_factory=list)


@dataclass
class SnapshotDiff:
    store_url: str
    domain: str
    old_timestamp: str
    new_timestamp: str
    new_products: List[Product] = field(default_factory=list)
    removed_products: List[Product] = field(default_factory=list)
    modified_products: List[ProductChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new_products or self.removed_products or self.modified_products)

    @property
    def total_changes_count(self) -> int:
        return len(self.new_products) + len(self.removed_products) + len(self.modified_products)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_url": self.store_url,
            "domain": self.domain,
            "old_timestamp": self.old_timestamp,
            "new_timestamp": self.new_timestamp,
            "has_changes": self.has_changes,
            "summary": {
                "new_products_count": len(self.new_products),
                "removed_products_count": len(self.removed_products),
                "modified_products_count": len(self.modified_products),
            },
            "new_products": [p.to_dict() for p in self.new_products],
            "removed_products": [p.to_dict() for p in self.removed_products],
            "modified_products": [
                {
                    "product_id": m.product_id,
                    "title": m.title,
                    "handle": m.handle,
                    "url": m.url,
                    "title_changed": m.title_changed,
                    "old_title": m.old_title,
                    "new_title": m.new_title,
                    "tags_added": m.tags_added,
                    "tags_removed": m.tags_removed,
                    "price_changes": [
                        {
                            "variant_id": pc.variant_id,
                            "variant_title": pc.variant_title,
                            "old_price": pc.old_price,
                            "new_price": pc.new_price,
                            "diff": pc.diff,
                            "diff_pct": pc.diff_pct,
                            "old_compare_at": pc.old_compare_at,
                            "new_compare_at": pc.new_compare_at,
                        }
                        for pc in m.price_changes
                    ],
                    "availability_changes": [
                        {
                            "variant_id": ac.variant_id,
                            "variant_title": ac.variant_title,
                            "old_available": ac.old_available,
                            "new_available": ac.new_available,
                        }
                        for ac in m.availability_changes
                    ],
                }
                for m in self.modified_products
            ],
        }
