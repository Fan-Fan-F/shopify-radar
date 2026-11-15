# Shopify Radar — 带定时监控的 Shopify 竞品选品雷达

> 定期抓取 Shopify 目标店铺商品，与历史快照做多维度差异比对（新品上架、价格变动、下架），并输出人类可读的变动报告。

---

## 目录
- [中文文档](#中文文档)
  - [项目背景与原思路关系](#项目背景与原思路关系)
  - [功能特性](#功能特性)
  - [快速开始](#快速开始)
  - [CLI 使用指南](#cli-使用指南)
  - [来源与致谢](#来源与致谢)
  - [许可证](#许可证)
- [English Documentation](#english-documentation)
  - [Background & Relation to Original Idea](#background--relation-to-original-idea)
  - [Features](#features)
  - [Quick Start](#quick-start)
  - [CLI Usage](#cli-usage)
  - [Provenance & Acknowledgments](#provenance--acknowledgments)
  - [License](#license)

---

# 中文文档

## 项目背景与原思路关系

原项目 [shopify-spy](https://github.com/ndgigliotti/shopify-spy) 是一个用于抓取 Shopify / WooCommerce 店铺商品与集合的批量数据爬取工具。

本项目 **Shopify Radar** 遵循开源重写路线 B（全新代码重写）。我们借鉴了原项目基于 Shopify 公开端点解析商品、图片和集合的优秀思路，但将定位从「一次性抓取工具」全面升级为**「动态选品监控雷达」**：
1. **代码全新实现**：零复用原项目任何源码，采用轻量化 Python 标准库架构，无强制外部依赖。
2. **新增快照生命周期管理**：每次抓取结构化落盘为带时间戳的历史快照（JSON 格式）。
3. **新增多维度差异分析引擎**：可细粒度比对两次快照，精准追踪新品上架、下架商品、变体价格升降幅、库存状态切换以及标题标签调整。
4. **新增多格式变动报告输出**：支持控制台格式化展示、Markdown 报告导出（方便团队推送与归档）以及结构化 JSON 输出。
5. **新增持续定时巡检雷达**：内置 `monitor` 循环调度器，实现周期性无人值守监控与变动即时告警。

---

## 功能特性

- 🔍 **商品与集合抓取**：基于 Shopify 标准端点，自动遍历分页抓取全量在售商品、多规格变体、价格及图片列表。
- 📦 **历史快照存储 (Snapshots)**：以标准 JSON 格式持久化多期店铺快照，支持按域名快速检索历史快照。
- ⚡ **差异比对引擎 (Diff Engine)**：
  - **新品上架**：识别新增商品 Handle、标题、售价与标签。
  - **下架检测**：识别在店铺中被下架或删除的商品。
  - **价格升降追踪**：细化到变体（Variant）粒度，记录调整前价格、现价、涨跌金额与变动百分比。
  - **库存变动监测**：监测商品变体是否售罄（In Stock 变为 Out of Stock）或重新补货。
  - **元数据变更**：捕捉标题更名、标签增删等关键信息。
- 📊 **人类可读报告 (Reports)**：
  - 控制台友好打印：清晰的分节与摘要统计。
  - Markdown 导出：一键生成排版工整的 Markdown 简报。
  - JSON 输出：便于接入告警机器人（飞书/钉钉/Webhook）或二次开发。
- ⏱️ **自动化监控循环 (Monitor Loop)**：支持自定义轮询间隔（例如每隔 300 秒），自动比对前次快照并播报变动。
- 🛡️ **网络韧性**：请求内置超时控制（Timeout）与指数退避重试（Exponential Backoff Retry），内置随机 User-Agent 规避基础风控。

---

## 快速开始

### 1. 环境准备
项目基于 Python 3.8+ 开发，核心功能全部使用 Python 标准库实现，零强制第三方依赖。

```bash
# 进入项目目录
cd shopify-radar

# （可选）安装为本地命令行工具
pip install -e .
```

### 2. 常用操作速览

```bash
# 1. 快速探测目标店铺连通性与商品样例
python3 -m shopify_radar peek https://example-store.myshopify.com

# 2. 抓取目标店铺并保存首份基准快照
python3 -m shopify_radar fetch https://example-store.myshopify.com

# 3. 查看该店铺的历史快照列表
python3 -m shopify_radar snapshots example-store.myshopify.com

# 4. 再次抓取店铺生成最新快照后，对比最近两期差异
python3 -m shopify_radar diff example-store.myshopify.com

# 5. 导出 Markdown 变动报告文件
python3 -m shopify_radar diff example-store.myshopify.com -f markdown -o changes.md

# 6. 启动无人值守监控雷达（每 5 分钟轮询一次，仅在有变动时输出）
python3 -m shopify_radar monitor https://example-store.myshopify.com --interval 300 -q
```

---

## CLI 使用指南

```text
usage: shopify-radar [-h] [-v] {fetch,diff,snapshots,monitor,peek} ...

子命令说明：
  fetch        抓取店铺商品并归档为快照
  diff         比对两次快照差异（支持文件路径或店铺域名）
  snapshots    列出本地保存的历史快照
  monitor      持续定时巡检监控店铺并实时播报变动
  peek         快速试探店铺端点连通性
```

### 常用命令参数

- **`fetch <url>`**
  - `-n, --limit <int>`: 限制抓取商品数量（常用于测试）。
  - `--snapshots-dir <dir>`: 快照保存目录（默认 `./snapshots`）。
  - `--download-images <dir>`: 同时将商品关联图片下载到指定文件夹。
  - `--timeout <float>`: 请求超时时间（默认 15 秒）。
  - `--retries <int>`: 失败重试次数（默认 3 次）。

- **`diff <target> [new_snapshot]`**
  - `target`: 店铺域名（自动比对最新两期）或旧快照 JSON 路径。
  - `new_snapshot`: 可选新快照 JSON 路径。
  - `-f, --format {terminal,markdown,json}`: 输出格式（默认 terminal）。
  - `-o, --output <path>`: 保存报告到文件。

- **`monitor <url>`**
  - `-i, --interval <int>`: 轮询周期秒数（默认 300 秒）。
  - `-q, --quiet-no-change`: 仅在检测到变动时输出，减少终端噪音。
  - `--export-md <path>`: 检测到变动时自动将变动报告更新到该 Markdown 文件。
  - `--max-runs <int>`: 最大轮询次数（默认持续运行）。

---

## 来源与致谢

本项目的思路与功能设计受到 [shopify-spy](https://github.com/ndgigliotti/shopify-spy) 启发，代码为独立实现。
原项目由 Nick Gigliotti (ndgigliotti) 以 MIT 许可证开源。

---

## 许可证

本项目沿用原项目的 MIT 开源许可证。全文见根目录 [LICENSE](LICENSE)。

---

# English Documentation

## Background & Relation to Original Idea

The original project [shopify-spy](https://github.com/ndgigliotti/shopify-spy) is a command-line tool and Python library for dumping products and collections from Shopify and WooCommerce stores.

**Shopify Radar** is a clean-room rewrite following Route B (Rewrite based on ideas). While inspired by `shopify-spy`'s concept of leveraging public Shopify JSON endpoints, `shopify-radar` transforms the concept from a static scraper into an **active product monitoring radar**:
1. **Fresh Implementation**: Zero code copied from the original project. Designed with Python standard library for robust, zero-dependency operations.
2. **Snapshot Lifecycle Management**: Every scrape is persisted as a structured, timestamped JSON snapshot.
3. **Multi-dimensional Diffing Engine**: Compares snapshots to identify new arrivals, delisted items, variant-level price adjustments (+/-%), stock availability changes, and metadata updates.
4. **Rich Change Reports**: Supports clean terminal cards, formatted Markdown exports, and machine-readable JSON.
5. **Periodic Watcher / Radar**: Built-in `monitor` loop for scheduled, unattended competitor tracking.

---

## Features

- 🔍 **Store Scraper**: Clean extraction of all active products, variants, pricing, tags, and images via standard Shopify endpoints.
- 📦 **Snapshot Persistence**: Automated versioning under `snapshots/<domain>/` with metadata headers.
- ⚡ **Granular Diff Engine**:
  - **New Arrivals**: Detect newly launched products with prices and tags.
  - **Delisted Products**: Flag removed or archived products.
  - **Price Tracking**: Track variant price drops and increases with exact amounts and percentage fluctuations.
  - **Inventory Shifts**: Track out-of-stock and back-in-stock state transitions.
  - **Metadata Changes**: Track title changes and tag additions/removals.
- 📊 **Human-Readable Reports**:
  - Terminal formatted view with summary counts and highlighted differences.
  - Markdown report export for easy sharing with teams.
  - JSON output for programmatic downstream integrations.
- ⏱️ **Scheduled Radar**: Automated background loop that fetches, diffs, and alerts on changes.
- 🛡️ **Resilience**: Configurable timeouts, exponential backoff retries, and randomized User-Agents.

---

## Quick Start

### 1. Installation
Requires Python 3.8+. No external dependencies required for core functionality.

```bash
cd shopify-radar

# Optional: editable install
pip install -e .
```

### 2. Common Workflows

```bash
# 1. Quick probe connectivity
python3 -m shopify_radar peek https://example-store.myshopify.com

# 2. Fetch baseline snapshot
python3 -m shopify_radar fetch https://example-store.myshopify.com

# 3. List snapshots for store
python3 -m shopify_radar snapshots example-store.myshopify.com

# 4. Fetch updated snapshot and compare differences
python3 -m shopify_radar diff example-store.myshopify.com

# 5. Export Markdown report
python3 -m shopify_radar diff example-store.myshopify.com -f markdown -o report.md

# 6. Continuous monitoring loop (check every 5 minutes)
python3 -m shopify_radar monitor https://example-store.myshopify.com --interval 300 -q
```

---

## Provenance & Acknowledgments

本项目的思路与功能设计受到 [shopify-spy](https://github.com/ndgigliotti/shopify-spy) 启发，代码为独立实现。
The original project was created by Nick Gigliotti (ndgigliotti) under the MIT License.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file in the repository root for details.
