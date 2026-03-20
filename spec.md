全球新闻-金融市场影响多 Agent 系统 V1
Summary
目标：构建一个面向专业交易者/研究员的“早盘研究生产线”，每天北京时间 07:00 前自动生成中文日报，覆盖中国市场与全球宏观驱动。
覆盖范围：A 股指数与重点板块、国内期货、黄金、白银、原油，并纳入美元、美债、全球风险偏好、中国政策与海外宏观事件作为传导因子。
输出边界：产出“方向 + 情景 + 风险”的专业策略建议；不做自动交易，不做个股级全面推荐，不给入场/止损/仓位。
交付形态：以 Markdown 为事实源，渲染 PDF 作为交付件；自动发布，保留审计链路与人工复核入口。
技术路线：Python + LangGraph 作为主编排；LiteLLM 做多模型统一接入；LangSmith 做 tracing/eval；AgentScope 暂不作为核心编排，只保留为后续实验/扩展选项。
Key Changes
定义 9 个核心 Agent：新闻采集、清洗去重/翻译、事件抽取、可信度评分、资产映射、领域分析（A 股/商品贵金属/原油能源/宏观汇率利率）、跨资产策略整合、证据审计、报告生成。
采用 LangGraph 状态图编排：定时任务触发 -> 多源采集 -> 聚类归一 -> 事件结构化 -> 分市场分析 -> 交叉校验 -> 审计门禁 -> 报告发布 -> 事后回溯。
新闻源采用“分级可信源”策略：官方披露与头部财经媒体为主；社媒仅作为线索池，未经二次验证不得进入正式结论。
中英双语优先：英文主流财经源与中文政策/本地源统一翻译、去重、聚类，形成 CanonicalNewsEvent。
每个核心结论必须可追溯：附来源、发布时间、可信度、传导链、反证条件；证据不足时只能降级为“观察项”，不得进入策略建议。
保留全链路数据：原始新闻、事件对象、Agent 中间产物、最终结论、发布时间、后验市场表现，支持 D0/D1/D5 回溯评估。
Public APIs / Interfaces / Types
统一 Source Adapter 接口：fetch(window) -> list[RawNewsItem]，支持 RSS、网页抓取、公开 API、后续付费源接入。
核心结构化对象：RawNewsItem、CanonicalNewsEvent、CredibilityScore、MarketImpactAssessment、DailyMarketBrief、ForecastOutcome。
MarketImpactAssessment 至少包含：影响资产、方向、置信度、影响期限、传导路径、关键证据、反证条件、观察指标。
DailyMarketBrief 至少包含：隔夜重点、核心事件、跨资产主线、A 股与板块观点、商品/贵金属/原油观点、风险情景、今日观察清单、证据附录。
配置面统一抽象：资产池、源白名单/分级、模型路由、发布时间、报告模板、评估窗口，避免把业务规则写死在 Agent prompt 中。
Test Plan
历史事件回放：FOMC、美国 CPI/非农、中国政策发布、地缘冲突、OPEC 会议，验证事件抽取、资产映射与报告成文质量。
双语归一测试：同一事件的中英文多源报道应聚为单个事件簇，且不能重复放大影响。
证据门禁测试：任何无引用或低可信来源支撑的结论，必须被拦截或降级为“观察项”。
鲁棒性测试：单个新闻源失败、单个模型失败、翻译失败时，系统仍能生成带缺失说明的降级报告。
评估测试：系统需正确记录预测方向与后验表现，并输出研究质量与可追溯性指标，而不只统计命中率。
Assumptions
默认时区与调度：Asia/Shanghai，每日 07:00 前完成发布。
默认报告语言：简体中文；新闻摄取语言：中文 + 英文。
V1 明确不做：盘中快讯、Web 仪表盘、全市场个股级映射、自动下单、必须依赖付费数据源。
默认粒度：资产类别 + 重点板块；若后续要扩展到自选标的，再新增 instrument-level 映射层。
框架选择依据：LangGraph 官方强调 durable execution、memory 与 human-in-the-loop；AgentScope 官方更适合 workflow/routing/handoffs/evaluation 能力补充；LiteLLM 官方提供多模型统一接口与 fallback/router；LangSmith 官方提供 tracing 与 offline/online evaluation。