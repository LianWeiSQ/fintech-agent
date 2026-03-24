# Fitech Agent 项目概览

## 一句话定义

Fitech Agent 是一个以 `Python 3.11+` 和 `LangGraph` 为基础的多 Agent 研究流水线：它围绕“手动触发一次研究运行”这个核心动作，优先收集黄金/白银主线相关的权威双语来源，完成归一化、事件抽取、可信度评估、资产影响映射、研究简报生成，并把完整链路写入 SQLite，供回放、审计和 D0 / D1 / D5 复盘使用。

## 1. 项目定位与当前边界

### 1.1 项目要解决什么问题

这个仓库的目标不是做一个泛化聊天机器人，而是做一个**可追溯的宏观研究执行引擎**。它关注的是：

- 新闻采集：产品主路径收束为 `L1 官方锚点 / L2 权威媒体 / L3 精选 X`，当前优先服务黄金与白银主线；底层仍支持 `file / rss / mock` adapter。
- 研究加工：把原始新闻压缩成结构化事件、可信度结论和跨资产观点。
- 输出交付：生成中文 Markdown 简报，并在可选依赖存在时输出 PDF。
- 审计回放：保存各阶段 payload，便于事后解释“这个结论是怎么来的”。

### 1.2 它现在更像什么

从实现状态看，Fitech Agent 更适合被理解为一个**可运行的多 Agent 研究原型 / v0-v1 框架**，而不是已经全面生产化的投研平台：

- 多 Agent 分层、审计链和扩展点已经具备。
- 默认 live 配置已经收束成贵金属优先的权威 source pack；离线样例运行则通过 `config/demo.toml` 完成。
- 核心分析逻辑目前仍主要由规则、启发式映射和阈值判断驱动。
- `LLM` 是可插拔增强层，不是系统运行的硬依赖。

### 1.3 当前不应高估的地方

- 本地 dashboard 存在，但它是轻量 HTTP 服务，不是通用生产 API。
- 数据存储可追溯，但 SQLite schema 还没有迁移体系。
- 研究链可运行，不代表研究质量、数据质量和生产稳定性已经封板。
- 部分中文界面文案与样例配置存在编码异常迹象，说明文档/前端层还需要进一步整理。

## 2. 对外入口与使用方式

### 2.1 CLI

项目主入口位于 `src/fitech_agent/cli.py`，对外暴露的命令包括：

| 命令 | 作用 |
| --- | --- |
| `init-db` | 初始化 SQLite 数据库 |
| `run` | 执行一次研究流水线 |
| `run-daily` | `run --mode full-report` 的兼容别名，已带弃用提示 |
| `evaluate` | 基于观测价格数据做 D0 / D1 / D5 结果评估 |
| `serve` | 启动本地 dashboard |

`run` 的关键运行参数：

- `--mode {full-report,collect-only}`：完整研究，或仅采集不出报告。
- `--triggered-at`：本次运行的锚定时间。
- `--lookback-hours`：相对窗口长度。
- `--window-start` / `--window-end`：显式时间窗，优先级高于 lookback。
- `--scope`：收缩下游分析范围。
- `--source`：收缩采集时启用的数据源。
- `--config`：指定配置文件。

### 2.2 Python API

项目也可以作为包内 API 调用，核心对外对象是：

- `ResearchPipeline`
- `NewsPipeline`（`ResearchPipeline` 的兼容别名）
- `ResearchRunRequest`
- `ResearchRunResult`

`ResearchPipeline.run()` 做的关键事情包括：

- 把 CLI / 调用侧请求规范化为内部请求对象。
- 推导时间窗。
- 校验 scopes 与 source allowlist。
- 执行 LangGraph 编排或顺序 fallback。
- 返回完整运行结果，包括原始新闻、中间结构、报告路径和降级原因。

### 2.3 LangGraph 接口

项目通过 `langgraph.json` 暴露两个 graph 名称：

- `research_run`
- `daily_brief`

它们当前都指向同一个 graph 入口 `src/fitech_agent/langgraph_app.py` 中的 `graph`。这意味着：

- 项目对 `LangGraph` 友好，可直接接入本地 `langgraph dev`。
- 如果本地环境没有安装 LangGraph，流水线仍可退化为顺序执行，不会因此完全不可用。

### 2.4 Dashboard HTTP

`src/fitech_agent/webapp.py` 提供本地 HTTP 服务，当前接口包括：

- `GET /api/bootstrap`
- `POST /api/research/run`
- `POST /api/research/chat`

这层的定位是**本地可视化和交互壳层**，不是正式多租户服务接口。它更像开发演示面板或本地研究工作台。

## 3. 端到端运行链路

### 3.1 请求规范化

研究运行从 `ResearchRunRequest` 开始，支持两种时间窗表达：

1. 显式传入 `window_start + window_end`
2. 传入 `triggered_at + lookback_hours`

实现细节上：

- 显式时间窗优先。
- `window_start` 和 `window_end` 必须成对出现。
- 若未显式传入时间窗，则以 `triggered_at - lookback_hours` 生成窗口。
- 若未指定 `lookback_hours`，使用配置中的默认值，默认是 `18` 小时。
- 时间在内部统一收敛到 ISO 时间戳，窗口边界最终转成 UTC 字符串。

### 3.2 编排主链

顶层研究流的节点顺序如下：

1. `start_run`
2. `ingestion`
3. `event_intelligence`
4. `market_reasoning`
5. `audit`
6. `report`

若 `mode = collect_only`，则在 `ingestion` 之后直接走 `finish_collect_only` 结束，不进入后续分析和报告阶段。

### 3.3 运行结果输出

一次完整运行最终会产生以下几类结果：

- 内存中的 `ResearchRunResult`
- SQLite 中的 `runs`、`stage_payloads`、`reports`、`outcomes`
- 报告目录中的 Markdown 文件
- 可选 PDF 文件
- dashboard 可消费的前端 payload

## 4. 模块分层与职责

### 4.1 配置层

配置入口在 `src/fitech_agent/config.py`，默认配置文件是 `config/example.toml`。这一层负责：

- 读取 `TOML`
- 读取本地 `.env`
- 解析 sources、audit 阈值、模型路由、run defaults
- 为每个 source 自动补齐信任等级、优先级、元数据

当前默认配置的产品表达已经从“广谱 RSS 订阅”收束为“权威来源分层”：

- `L1 官方锚点`：Fed、PBOC、NBS、CME
- `L2 权威媒体`：Reuters
- `L3 精选 X`：Reuters Markets、Bloomberg Markets、Nick Timiraos、Javier Blas

配置中最重要的几块是：

- `sources`
- `audit`
- `model_route`
- `agent_routes`
- `run_defaults`
- `skill_dirs`

### 4.2 数据模型层

核心类型集中在 `src/fitech_agent/models.py`，其中最关键的是：

- `RawNewsItem`：原始新闻条目
- `NewsCluster`：归一化后的新闻簇
- `CanonicalNewsEvent`：标准化事件
- `CredibilityScore`：可信度评分
- `EventAssetMap`：资产映射结果
- `MarketImpactAssessment`：市场影响评估
- `ResearchBrief`：研究简报
- `ResearchRunRequest` / `ResearchRunResult`
- `ForecastOutcome`：事后评估结果

这些类型构成了项目从采集、分析到交付的主数据链。

### 4.3 Source Adapters

source 抽象位于 `src/fitech_agent/adapters/base.py`，当前实现包括：

- `file`：从本地 JSON 读样例新闻
- `rss`：抓取 RSS / Atom feed
- `mock`：用于失败注入或测试

其中 `rss` 适配器是实现细节，不再作为产品概念暴露；产品层统一把来源表达成“官方锚点 / 权威媒体 / 精选 X”。底层 `rss` 适配器内置了较多过滤逻辑：

- 标题关键词 allowlist / blocklist
- 作者 allowlist
- link 域名校验
- summary 中链接域名校验
- 时间窗过滤

这使得 source 层不是“抓什么算什么”，而是自带一层前置筛选。

### 4.4 五个 Core Agents

当前仓库的核心研究流水线由五个 agent 组成，每个 agent 目录都有 `agent.py`、`runtime.py`、`prompts.py`、`steps/`、`skill.md` 等文件。

#### `ingestion`

职责：

- 选择 source
- 执行采集
- 原始去重
- 记录 raw evidence
- 汇总采集阶段降级原因

输出：

- `CollectedNewsBatch`

#### `event_intelligence`

职责：

- 对原始新闻做归一化和聚类
- 提取标准化事件
- 必要时做翻译/摘要
- 按 source mix 计算可信度

输出：

- `EventIntelligenceBundle`

实现上，这一层虽保留了 `LiteLLMClient` 接口，但事件抽取和可信度主逻辑仍主要依赖规则，不是纯 LLM 驱动。

#### `market_reasoning`

职责：

- 把事件映射到资产、板块和宏观因子
- 根据 `scope` 裁剪下游分析范围
- 对不同 domain 生成市场影响评估
- 汇总跨资产观点

输出：

- `MarketReasoningBundle`

当前的 domain analysis 和 strategy integration 仍是较明确的规则系统。

#### `audit`

职责：

- 结合可信度和评估置信度做 publishability gate
- 生成 downgrade trace
- 汇总 degraded reasons

输出：

- `AuditBundle`

这层确保“观点是否可发布”与“观点是否可观察”被显式区分。

#### `report`

职责：

- 基于 audited assessments 生成 `ResearchBrief`
- 输出 Markdown
- 可选输出 PDF
- 落库保存报告信息

输出：

- `ReportBundle`

### 4.5 编排层

编排逻辑位于 `src/fitech_agent/orchestration.py` 与 `src/fitech_agent/pipeline.py`：

- 有 LangGraph 时，构建状态图。
- 无 LangGraph 时，执行顺序 fallback。
- 内部状态使用一个统一的 `PipelineState` / state dict 在各节点之间传递。

这个设计的优点是：

- 可以本地轻量跑通。
- 可以逐步过渡到更规范的图式编排。
- 可以在不改变上层接口的情况下替换部分节点实现。

### 4.6 存储层

存储层位于 `src/fitech_agent/storage.py`，当前是 SQLite 单文件设计，核心表有四张：

| 表 | 用途 |
| --- | --- |
| `runs` | 记录每次运行的时间窗、模式、source、状态、配置等 |
| `stage_payloads` | 保存各阶段 payload，是审计和回放的主体 |
| `reports` | 保存报告 payload 与产物路径 |
| `outcomes` | 保存 D0 / D1 / D5 的事后评估结果 |

其中最有特色的是 `stage_payloads`：

- 每条记录都带 `stage`
- 可以带 `agent_id`
- 可以带 `substage`
- 还会记录 `entity_type`、`entity_id` 与完整 `payload_json`

这让系统能够追溯“哪个 agent 的哪个 substage 在什么时候产出了哪类实体”。

### 4.7 报告层

报告相关逻辑主要在 `src/fitech_agent/agents/report/` 和 `src/fitech_agent/reporting.py`：

- 先生成结构化 `ResearchBrief`
- 再渲染为 Markdown
- 若安装 `ReportLab`，则把 Markdown 转成 PDF

报告中包含：

- 概览
- 重点线索
- 核心事件
- 跨资产主线
- 各类资产观点
- 风险情景
- 观察清单
- 证据附录
- 降级说明

### 4.8 Dashboard / Web 层

本地 dashboard 的主要职责不是重新分析，而是把已有结果组织成更适合前端消费的 payload，包括：

- source catalog
- source mix
- source classes
- workflow 可视化
- domain boards
- timeline
- watchlist
- report sections
- 简单问答上下文

如果本地模型可用，dashboard 问答可以得到增强；不可用时则走 fallback 文本生成。

### 4.9 Evaluation 层

`src/fitech_agent/evaluation.py` 负责把存储中的 audited assessments 与价格观测 CSV 对齐，生成：

- `D0`
- `D1`
- `D5`

三个窗口的命中结果。它不是回测框架，而是一个较轻量的**预测结果核验层**。

### 4.10 Skills Overlay 机制

这是仓库里一个很有辨识度的设计。

内置 skill 位于：

- `src/fitech_agent/agents/<agent_id>/skill.md`

外部 overlay 位于：

- `skills/agents/<agent_id>/`
- `skills/<pack>/agents/<agent_id>/`

加载器会把：

- skill 正文
- references
- checklists
- templates
- examples

组合进 agent prompt context。换句话说，这套机制更接近“面向 agent 的可版本化知识/提示叠加层”，而不是 Python 插件系统。

## 5. 当前实现的关键行为与设计取舍

### 5.1 时间窗行为

当前实现明确区分：

- 触发时刻 `triggered_at`
- 分析窗口 `window_start` / `window_end`

这使流水线更适合“任意时间手动触发”的研究模式，而不是被写死在早盘定时任务上。

### 5.2 `source` 与 `scope` 的边界

- `source` 只影响采集阶段启用哪些 source adapter。
- `scope` 不影响采集，只影响资产映射之后的下游分析与报告输出。

这是当前实现里很重要的行为边界，测试也覆盖了这一点。

### 5.3 降级而非硬失败

项目在设计上偏向“能完成就完成，并把不足显式记录下来”，典型例子包括：

- 单个 source 失败时，整体运行仍可完成。
- 没有高等级 source anchor 时，会记录 degraded reason。
- PDF 渲染失败不会阻断 Markdown 报告写出，只会追加 warning。

### 5.4 当前更偏规则系统

虽然项目引入了 `LiteLLMClient`，但代码现状表明：

- 归一化依赖词典替换和 key derivation。
- 事件类型识别、bias 判定、region 判定以规则为主。
- 可信度评分是 source tier 权重 + bonus / penalty 公式。
- 资产映射、domain 方向、策略整合都主要由显式规则完成。

因此，当前仓库的真实优势不在“模型推理特别强”，而在“流程稳定、结构明确、便于审计和演进”。

## 6. 质量现状与验证结果

### 6.1 当前健康度

在当前仓库上执行 `pytest -q`，结果为：

- `31 passed`
- 1 条 `.pytest_cache` 权限 warning

这个结果说明核心路径可运行，但不应被解读为“已经生产可用”。

### 6.2 现有测试重点

测试覆盖的主要场景包括：

- 端到端报告生成
- `collect_only` 分支
- `scope` 过滤只影响下游分析
- `source` allowlist 只影响采集
- 显式时间窗优先于 lookback
- 单 source 失败时的降级完成
- `run-daily` 兼容与弃用提示
- CLI 参数校验
- dashboard bootstrap / run / chat payload
- `sourceCatalog / sourceMix` 的 `L1/L2/L3 + sourceClass` 契约
- `L3 精选 X` 不会在 source mix 展示中压过 `L1/L2` 锚点
- RSS 作者、关键词、链接域名过滤
- source trust profile 推导
- audit publishability gate

也就是说，仓库在“主流程正确性”和“配置/过滤行为边界”上已经有比较明确的回归网。

## 7. 已验证运行路径

如果只按仓库当前已验证路径来跑，建议使用：

1. 离线路径：通过 `config/demo.toml` 加载 `examples/sample_news.json`
2. live 路径：通过 `config/example.toml` 加载贵金属优先的权威来源包
3. 使用本地 SQLite 文件保存结果
4. 生成 Markdown 报告
5. 若环境中安装了 `ReportLab`，再附加 PDF 输出
6. 若需要可视化，再启动本地 `serve`

这条路径的优点是：

- 不依赖外部网络
- 不依赖模型密钥
- 便于调试与交接

## 8. 规格与实现差异

当前代码与规格/直觉之间，最值得显式说明的几个差异如下：

### 8.1 “不做 Web 服务”与本地 dashboard 并存

`spec.md` 的产品边界强调不做 HTTP API / Web 服务，但当前实现已经包含本地 dashboard 和 HTTP handler。更准确的表述应当是：

- 当前没有面向生产环境的通用服务端 API
- 但已经提供了本地可视化交互入口

### 8.2 “9 个逻辑阶段”被实现为 “5 个 core agents + substages”

规格里更像是在描述逻辑研究阶段，而当前实现则收敛为：

- 5 个 core agents
- 每个 agent 内再拆 substage

这不是功能缺失，而是工程打包方式不同。

### 8.3 LLM 是增强层，不是分析主干

从命名上看，这个项目容易被误以为是强模型驱动研究系统；但代码现状更接近：

- 规则主干
- 模型补强

因此，对项目能力的预期应以代码现状为准，而不是以抽象名称为准。

## 9. 当前优势、风险与后续演进方向

### 9.1 当前优势

- 结构清晰：配置、编排、agent、存储、报告、dashboard 分层明确。
- 审计完整：`agent_id + substage` 让链路可回放、可解释。
- 产品收束更清晰：默认消息源已经压缩为 13 个贵金属优先的权威来源。
- 离线友好：`config/demo.toml` 仍可让仓库开箱可用。
- 扩展点明确：source adapters、agent routes、skill overlays 都是自然扩展位。
- 回归基础已具备：关键主流程已有测试保护。

### 9.2 当前风险与限制

- 规则驱动偏重，研究表达的灵活性和复杂推理能力有限。
- SQLite 无迁移设计，长期演进可能产生 schema 管理压力。
- source 配置已经明显收敛，但后续扩展到更多资产包时仍需要模板化管理。
- dashboard 是本地轻服务，缺少权限、任务队列、持久会话等能力。
- 部分中文字符串存在编码异常，影响产品化质量。

### 9.3 合理的下一步演进方向

- 把高价值规则逐步替换为“规则 + 模型结构化输出”的混合模式。
- 为 SQLite 增加 schema version 和迁移机制。
- 收敛/模板化 source 配置，降低维护成本。
- 对 dashboard 做编码与文案清理，提升演示与交付质量。
- 增加更多运行可观测性，例如阶段耗时、source 命中率、错误分布。

## 10. 总结

如果把 Fitech Agent 放在一个准确的位置上，它是一个**围绕宏观新闻研究任务构建的、可运行、可审计、可扩展的多 Agent 流水线框架**。它已经具备：

- 明确的研究主链
- 可追溯的数据存储
- 本地 CLI / LangGraph / dashboard 入口
- 可落地的报告输出

但它目前的核心竞争力仍然是**工程结构和审计能力**，不是最强的模型推理能力。对于首次接手的开发者和业务/研究同学来说，最合适的理解方式是：这是一个很好的研究引擎骨架，已经能稳定跑通核心链路，下一阶段重点在于提升模型化能力、可观测性和产品化完成度。



