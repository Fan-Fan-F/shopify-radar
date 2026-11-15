# shopify-radar 功能规格说明书 (SPEC.md)

## 1. 项目定位与背景

`shopify-radar` 是一款面向跨境电商、独立站运营与选品研究人员的 Shopify 店铺竞品监控雷达。
原项目 `shopify-spy` 专注于批量抓取公开端点数据，而 `shopify-radar` 在保持端点抓取与数据清洗能力的基础上，重构升级为具备「快照归档、差异比对、价格追踪、变动报告、定时巡检」的选品雷达系统。本项目采用全新架构与代码实现，完全独立开发（遵循路线 B 规范）。

---

## 2. 功能点清单

### 2.1 借鉴的功能点 (Derived from shopify-spy)
1. **Shopify 公开 JSON 端点抓取**:
   - 支持通过 Shopify 标准公开 API `/products.json` 批量抓取商品数据。
   - 支持分页抓取参数（`page`, `limit`，单页最高 250 件商品），自动遍历全量在售商品。
2. **店铺集合 (Collections) 抓取**:
   - 支持通过 `/collections.json` 抓取店铺商品集合与分类结构。
3. **商品图片提取与下载**:
   - 解析商品关联的全部高分辨率图片 URL，支持可选的本地图片保存下载功能。
4. **结构化数据清洗**:
   - 规范化店铺输出格式，提取商品的核心属性（ID、Handle、标题、Vendor、类型、标签、发布时间、更新时间、变体价格、对比价格、库存状态等），输出清晰规范的 JSON 格式。

### 2.2 新增与重构功能点 (New Features in shopify-radar)
1. **快照持久化系统 (Snapshot Storage)**:
   - 每次抓取自动归档为标准化 JSON 快照文件，存储在 `snapshots/<store_domain>/` 目录下。
   - 快照包含元数据头（抓取时间戳 UTC、店铺 URL、抓取商品总数、集合总数、耗时等）及标准化商品实体列表。
   - 提供快照管理接口，支持列出指定店铺的所有历史快照，方便回溯与版本追踪。
2. **商品多维度差异比对引擎 (Differential Comparison Engine)**:
   - **新品上架检测 (New Arrivals)**: 比对新旧两期快照，自动识别新增产品、上架时间、价格区间及标签。
   - **商品下架检测 (Delisted Products)**: 自动比对在旧快照存在但在新快照中消失的商品。
   - **价格变动追踪 (Price Changes)**: 深入到变体粒度（Variant Level），对比价格变化，计算变动绝对金额与涨跌百分比（如降价促销、提价），并跟踪 `compare_at_price`（原价）调整。
   - **库存状态变更 (Stock / Availability Shifts)**: 监控变体是否从有货转为售罄（Sold Out）或重新补货（Back in Stock）。
   - **商品元数据变更 (Metadata Changes)**: 检测商品标题修改、标签增删等关键信息改动。
3. **人类可读变动报告 (Human-Readable Reports)**:
   - 控制台终端格式化输出（带摘要卡片、统计指标、分节变动明细列表）。
   - Markdown 报告导出：支持自动生成 `.md` 变动简报，便于团队共享、推送飞书/钉钉或邮件存档。
   - JSON 结构化差异输出：便于二次开发和集成到外部监控告警系统。
4. **定时巡检雷达监控 (Continuous Monitor Mode)**:
   - 提供 `monitor` 子命令，支持以用户指定轮询周期（例如 `--interval 300` 秒）常驻监控目标店铺。
   - 每次巡检自动发起抓取 -> 持久化快照 -> 与前次快照对比 -> 产生变动时触发报告。
   - 支持 `--quiet-no-change` 参数，仅在检测到实际变动时输出提醒，降低终端噪音。
5. **网络韧性与安全防护 (Resilience & Anti-Blocking)**:
   - 内置请求超时配置（默认 15 秒，可配置）。
   - 具备重试机制与指数退避（默认最多 3 次重试），应对偶发网络抖动与 429/5xx 错误。
   - 内置 User-Agent 伪装，避免基础风控拦截。
6. **清晰模块化的 CLI 子命令**:
   - `fetch`: 抓取店铺并创建快照。
   - `diff`: 对比两份快照文件或店铺最近两期快照并输出差异报告。
   - `snapshots`: 列出目标店铺的历史快照。
   - `monitor`: 启动自动化周期监控循环。
   - `peek`: 快速探测并展示单个商品，验证店铺可达性与端点状态。

---

## 3. 技术架构与设计

### 3.1 目录结构
```text
shopify-radar/
├── PROVENANCE.md          # 溯源文件
├── SPEC.md                # 规格说明书与自测记录
├── README.md              # 中英双语用户文档
├── LICENSE                # MIT 开源许可证
├── pyproject.toml         # Python 打包与元数据配置
├── setup.py               # 兼容性安装脚本
├── shopify_radar/
│   ├── __init__.py        # 模块导出与版本号
│   ├── __main__.py        # python -m shopify_radar 入口
│   ├── cli.py             # CLI 命令行参数解析与子命令分发
│   ├── client.py          # 网络请求客户端（超时、重试、UA、Shopify API 抓取）
│   ├── models.py          # 核心数据模型（Product, Variant, Snapshot 等）
│   ├── storage.py         # 快照持久化与检索管理
│   ├── diff.py            # 差异比对分析核心算法
│   ├── reporter.py        # 终端与 Markdown 变动报告渲染器
│   └── monitor.py         # 定时巡检雷达调度器
├── tests/
│   ├── __init__.py
│   ├── test_diff.py       # 差异比对引擎单测
│   └── test_pipeline.py   # 抓取-快照-比对端到端自测用例
└── fixtures/              # 测试与离线验证用样例数据
    ├── store_v1_products.json
    └── store_v2_products.json
```

### 3.2 依赖说明
- 采用 Python 3 标准库（`urllib.request`, `json`, `argparse`, `dataclasses`, `time`, `pathlib` 等）编写核心引擎，零强制外部依赖即可独立运行，环境兼容性极高。
- 代码完全独立编写，严禁复用 `shopify-spy` 的任何源码文件或函数。

---

## 4. 自测记录

### 4.1 测试环境与方式
- **测试环境**: Linux x86_64, Python 3.12.3
- **隔离测试策略**: 采用内置测试夹具（`fixtures/v1_products.json` 与 `fixtures/v2_products.json`），启动本地轻量 HTTP Mock 服务模拟 Shopify 店铺端点，不依赖真实外网连接。
- **覆盖流程**: 连通性探测 (`peek`) → 初次抓取全量商品并归档 (`fetch` v1) → 快照检索 (`snapshots`) → 模拟店铺商品变动（降价、下架、新品、缺货）→ 二次抓取归档 (`fetch` v2) → 差异比对与终端报告 (`diff`) → Markdown 与 JSON 报告导出 → 定时巡检雷达循环 (`monitor` 2 轮)。

### 4.2 单元与流程自动化测试
- **测试命令**:
  ```bash
  python3 -m unittest discover -s tests -p "test_*.py" -v
  ```
- **测试结果**:
  ```text
  test_new_product_and_removed_product (test_diff.TestDiffEngine.test_new_product_and_removed_product) ... ok
  test_price_change_and_availability (test_diff.TestDiffEngine.test_price_change_and_availability) ... ok
  test_peek_and_fetch_pipeline (test_pipeline.TestShopifyRadarPipeline.test_peek_and_fetch_pipeline) ... ok

  ----------------------------------------------------------------------
  Ran 3 tests in 0.550s

  OK
  ```

### 4.3 完整 CLI 端到端链路实跑记录
- **测试脚本**: `scripts/run_selftest.py`
- **执行命令**:
  ```bash
  python3 scripts/run_selftest.py
  ```
- **实跑输出概要**:
  1. `peek` 成功识别店铺在线状态与样本商品元数据（ID: 1001, Ergonomic Office Chair, 变体价格 $199.99）。
  2. `fetch` (v1) 成功抓取 3 件商品与 1 个集合，存入快照 `snapshot_2026-11-15T14-51-13Z.json`。
  3. `snapshots` 成功检索到刚创建的历史快照。
  4. `fetch` (v2) 成功抓取变动后数据，存入新快照 `snapshot_2026-11-15T14-51-14Z.json`。
  5. `diff` 正确识别：
     - **新品上架 (1 件)**: `Heavy Duty Monitor Arm` ($79.99)
     - **下架商品 (1 件)**: `Bamboo Standing Desk`
     - **商品变动 (2 件)**:
       * `Ergonomic Office Chair Pro`: 标题更新，标签追加 `clearance, sale`，变体 Standard 价格从 $199.99 降至 $169.99 (-$30.00, -15.0%)，变体 Headrest 价格从 $229.99 降至 $219.99 (-$10.00, -4.3%)。
       * `Wireless Mechanical Keyboard`: 变体 `Brown Switch` 库存状态由 In Stock 变为 Out of Stock。
  6. `diff -f markdown -o report.md` 与 `-f json -o report.json` 导出完整成功。
  7. `monitor --max-runs 2 -q` 定时轮询监控两轮稳定退出。
- **自测结论**: 8/8 场景全部跑通通过（第 1 轮即通过，无须重试轮次）。

