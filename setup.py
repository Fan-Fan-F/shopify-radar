from setuptools import setup, find_packages

setup(
    name="shopify-radar",
    version="0.1.0",
    description="Shopify competitor monitoring radar with snapshot diffing, price tracking, and change reports.",
    author="shopify-radar contributors",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "shopify-radar=shopify_radar.cli:main",
        ],
    },
    python_requires=">=3.8",
)
