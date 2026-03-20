# Fitech Agent 手动触发研究流水线 Spec

## 1. 产品定位

Fitech Agent 是一个面向专业交易者与研究员的手动触发研究引擎，不再依赖固定的北京时间 07:00 定时任务。  
用户可以在任意时点主动发起一次研究运行，系统自动完成：

- 全球新闻采集
- 事件归一与结构化抽取
- 可信度与证据审计
- 跨资产市场影响分析
- 中文研究简报生成
- D0 / D1 / D5 复盘评估所需链路留存

首版聚焦以下研究范围：

- A 股指数与重点板块
- 国内期货
- 黄金、白银
- 原油与能源链
- 美元、美债
- 全球风险偏好
- 中国政策
- 海外宏观事件

## 2. 目标与边界

### 2.1 目标

- 把一次研究运行沉淀为完整、可追踪、可复盘的研究链路
- 支持默认全市场运行，也支持按 scope / source / 时间窗做局部运行
- 输出适合盘前、盘中、盘后使用的通用研究简报，而不是只服务早盘场景

### 2.2 非目标

- 不做自动定时调度
- 不做 HTTP API / Web 服务
- 不做自动交易、自动下单、仓位管理
- 不做个股级全面覆盖
- 不做主题关键词驱动的开放式研究助手

## 3. 运行模式

系统支持两种运行模式：

### 3.1 `full-report`

执行完整链路：

`start_run -> collect_news -> normalize_news -> extract_events -> score_credibility -> map_assets -> filter_scope -> analyze_domains -> integrate_strategy -> audit_evidence -> generate_report`

输出：

- 研究运行记录
- 原始新闻与各阶段 payload
- `ResearchBrief`
- Markdown / PDF 报告文件

### 3.2 `collect-only`

仅执行：

`start_run -> collect_news -> finalize`

输出：

- 研究运行记录
- 原始新闻与采集阶段 payload
- 不生成事件、评估、Markdown、PDF

## 4. 触发方式与接口

### 4.1 CLI

主命令：

```bash
fitech-agent run
```

支持参数：

- `--mode {full-report,collect-only}`
- `--triggered-at <ISO8601>`
- `--lookback-hours <int>`
- `--window-start <ISO8601>`
- `--window-end <ISO8601>`
- 重复 `--scope <value>`
- 重复 `--source <name>`
- `--config <path>`

兼容入口：

```bash
fitech-agent run-daily
```

说明：

- `run-daily` 是兼容别名
- 内部等价于 `run --mode full-report`
- 会输出 deprecation 提示

### 4.2 Python API

主入口：

- `ResearchPipeline`

请求模型：

- `ResearchRunRequest`

返回模型：

- `ResearchRunResult`

兼容别名：

- `NewsPipeline = ResearchPipeline`

## 5. 时间窗规则

系统统一用 `triggered_at` 作为运行时间锚点。

优先级如下：

1. 如果同时传入 `window_start` 和 `window_end`，直接使用显式窗口
2. 否则使用 `triggered_at - lookback_hours` 生成窗口
3. 如果未传 `lookback_hours`，使用配置中的默认值

约束：

- `window_start` / `window_end` 必须成对出现
- 单边传入时报错
- `window_start < window_end`
- 默认时间窗为 `triggered_at` 往前 18 小时

## 6. Scope 与 Source 语义

### 6.1 Scope

合法值固定为：

- `equity`
- `commodities`
- `precious_metals`
- `crude_oil`
- `usd`
- `ust`
- `risk_sentiment`
- `cn_policy`
- `global_macro`

规则：

- 未传时默认覆盖全部 scope
- `scope` 只影响下游事件、映射、分析与报告
- `scope` 不影响 source 的采集 allowlist

### 6.2 Source

`source` 是 source name allowlist。

规则：

- 未传时默认使用全部启用的数据源
- 只影响采集阶段选择哪些 source adapter
- 不改变后续分析逻辑

## 7. 核心 Agent 链路

系统保留 9 个核心 Agent：

1. 新闻采集 Agent
2. 归一化 / 去重 Agent
3. 事件抽取 Agent
4. 可信度评分 Agent
5. 资产映射 Agent
6. 领域分析 Agent
7. 跨资产整合 Agent
8. 证据审计 Agent
9. 报告生成 Agent

其中新增一个显式的 `filter_scope` 阶段，用于在资产映射之后、领域分析之前完成范围裁剪。

## 8. 数据模型

### 8.1 Public Types

- `RawNewsItem`
- `CanonicalNewsEvent`
- `CredibilityScore`
- `EventAssetMap`
- `MarketImpactAssessment`
- `ResearchRunRequest`
- `ResearchBrief`
- `ResearchRunResult`
- `ForecastOutcome`

### 8.2 `ResearchRunRequest`

字段：

- `mode`
- `triggered_at`
- `lookback_hours`
- `window_start`
- `window_end`
- `scopes`
- `sources`

### 8.3 `ResearchBrief`

`ResearchBrief` 是新的主报告模型，用来替代早期的 `DailyMarketBrief`。

必须包含：

- `triggered_at`
- `window_start`
- `window_end`
- `mode`
- `scopes`
- `sources`
- `overview`
- `overnight_focus`
- `core_events`
- `cross_asset_themes`
- `equity_view`
- `commodities_view`
- `precious_metals_view`
- `crude_oil_view`
- `risk_scenarios`
- `watchlist`
- `evidence_appendix`
- `degraded_reasons`

兼容策略：

- 代码中保留 `DailyMarketBrief = ResearchBrief` 别名
- 新实现统一以 `ResearchBrief` 为主

### 8.4 `ResearchRunResult`

必须包含：

- `run_id`
- `mode`
- `triggered_at`
- `window`
- `scopes`
- `sources`
- `raw_items`
- `clusters`
- `events`
- `credibility_scores`
- `mappings`
- `assessments`
- `integrated_view`
- `audit_notes`
- `degraded_reasons`
- `report`
- `markdown_path`
- `pdf_path`

## 9. 报告产物

### 9.1 报告视图

报告标题从“早盘研究简报”升级为“研究简报”。

首段固定为“本次触发概览”，至少输出：

- `triggered_at`
- `window`
- `mode`
- `scope`
- `source`

其余章节保留当前研究结构：

- 重点线索
- 核心事件
- 跨资产主线
- A 股与重点板块
- 商品期货
- 贵金属
- 原油与能源
- 风险情景
- 观察清单
- 证据附录
- 降级说明

### 9.2 文件命名

报告文件统一命名为：

- `research_run_<run_id>.md`
- `research_run_<run_id>.pdf`

不再使用 `daily_brief_*` 命名。

## 10. 配置

配置继续使用 TOML。

### 10.1 保留配置

- `timezone`
- `report_language`
- `database_path`
- `report_dir`
- `[audit]`
- `[model_route]`
- `[[sources]]`

### 10.2 新增配置

```toml
[run_defaults]
mode = "full_report"
lookback_hours = 18
```

说明：

- 旧的 `report_time` 调度语义已废弃
- 默认运行模式为 `full_report`
- 默认时间窗回看 18 小时

## 11. 存储与链路留存

SQLite 继续作为首版审计存储。

### 11.1 runs 表核心字段

- `triggered_at`
- `mode`
- `window_start`
- `window_end`
- `scopes_json`
- `sources_json`
- `status`
- `degraded`
- `degraded_reasons`
- `config_json`

### 11.2 兼容策略

- 不做旧 schema 自动迁移
- 现有本地数据库视为可重建资产
- 如旧库缺少新字段，提示删除数据库后重新初始化

## 12. LangGraph 入口

主图名更新为：

- `research_run`

兼容保留：

- `daily_brief`

两者当前都指向同一图入口，便于本地调试脚本过渡。

## 13. 评估与验收

### 13.1 CLI 验收

- `fitech-agent run` 默认可成功生成 full-report
- `fitech-agent run --mode collect-only` 只采集、不出报告
- `--window-start/--window-end` 优先级高于 `--lookback-hours`
- 只传单边窗口参数时报错
- `run-daily` 仍可执行且有 deprecation 提示

### 13.2 Python API / 模型验收

- `ResearchRunRequest` 默认值可继承 `run_defaults`
- `scope` 只裁剪下游分析与报告
- `source` 只裁剪采集阶段
- `ResearchBrief` 可正常序列化、存储、渲染

### 13.3 业务链路验收

- full-report 模式继续支持端到端样例
- collect-only 模式不会生成 Markdown / PDF
- source 失败时，full-report 可以降级完成
- collect-only 遇到 source 失败时也会记录 degraded reason
- D0 / D1 / D5 评估仍基于 `run_id` 工作

## 14. 当前默认值

- 默认入口：`fitech-agent run`
- 默认模式：`full_report`
- 默认时间窗：向前 18 小时
- 默认 scope：全量 scope
- 默认 source：所有启用 source

## 15. 后续演进方向

- 增加 HTTP API / 服务化封装
- 支持主题驱动或关键词驱动的临时研究运行
- 增加更多实时数据源与行情源
- 补充更细粒度的资产映射与指标观测
- 引入更完善的 schema migration 与运行观测体系
