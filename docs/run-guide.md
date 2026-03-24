# Fitech Agent 运行说明

## 1. 环境要求

- Python `3.11+`
- 建议使用 Windows PowerShell
- 首次安装依赖时需要联网
- 如果只跑离线 demo，不需要模型密钥
- 如果要抓取 live 消息源，需要网络可访问对应站点

## 2. 安装项目

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

如果 PowerShell 阻止激活脚本，可以临时执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. 两种推荐运行方式

### 3.1 离线 demo

这条路径最适合第一次验证项目是否能跑通。

- 使用配置文件：`config/demo.toml`
- 数据源：`examples/sample_news.json`
- 特点：不依赖外部消息源，适合本地 smoke test

初始化数据库：

```powershell
python -m fitech_agent init-db --config config/demo.toml
```

执行完整研究：

```powershell
python -m fitech_agent run --config config/demo.toml
```

只采集不出报告：

```powershell
python -m fitech_agent run --config config/demo.toml --mode collect-only
```

### 3.2 Live 权威消息源模式

这条路径使用当前默认的贵金属优先权威来源包。

- 使用配置文件：`config/example.toml`
- 默认来源分层：
  - `L1 官方锚点`
  - `L2 权威媒体`
  - `L3 精选 X`
- 当前重点：黄金、白银、利率、美元、Fed、PBOC、CME、Reuters

初始化数据库：

```powershell
python -m fitech_agent init-db --config config/example.toml
```

执行完整研究：

```powershell
python -m fitech_agent run --config config/example.toml
```

只采集不出报告：

```powershell
python -m fitech_agent run --config config/example.toml --mode collect-only
```

## 4. 常用运行参数

指定时间锚点：

```powershell
python -m fitech_agent run --config config/demo.toml --triggered-at 2026-03-24T08:00:00+08:00
```

指定回看窗口：

```powershell
python -m fitech_agent run --config config/demo.toml --lookback-hours 24
```

显式指定窗口：

```powershell
python -m fitech_agent run --config config/demo.toml --window-start 2026-03-23T00:00:00+08:00 --window-end 2026-03-24T08:00:00+08:00
```

收缩研究范围：

```powershell
python -m fitech_agent run --config config/example.toml --scope precious_metals --scope usd --scope ust
```

只启用部分来源：

```powershell
python -m fitech_agent run --config config/example.toml --source FedPressAll --source ReutersMarkets --source NickTimiraosX
```

## 5. 启动本地 Dashboard

启动服务：

```powershell
python -m fitech_agent serve --config config/demo.toml
```

默认地址：

```text
http://127.0.0.1:8010
```

如果你要用 live 来源包启动 dashboard：

```powershell
python -m fitech_agent serve --config config/example.toml
```

自定义 host 和 port：

```powershell
python -m fitech_agent serve --config config/demo.toml --host 127.0.0.1 --port 8010
```

## 6. 运行完成后会看到什么

命令行会输出：

- `Run ID`
- `Mode`
- `Triggered At`
- `Window`
- `Collected Items`
- `Sources`
- `Markdown`
- `PDF`

默认产物位置：

- 离线 demo 数据库：`artifacts/fitech_agent.demo.db`
- live 数据库：`artifacts/fitech_agent.db`
- demo 报告目录：`artifacts/reports-demo`
- live 报告目录：`artifacts/reports`

说明：

- Markdown 报告默认会生成
- PDF 依赖 `ReportLab`，如果环境不满足，输出可能显示 `not generated`
- 未接入模型时，系统会回退到规则路径，不会阻止主流程运行

## 7. 评估已有运行

对某次 run 做 D0 / D1 / D5 评估：

```powershell
python -m fitech_agent evaluate --config config/demo.toml --run-id 1 --prices-file examples/sample_price_observations.csv
```

## 8. 一个最短可跑通流程

如果你只是想最快看到结果，直接按下面执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m fitech_agent init-db --config config/demo.toml
python -m fitech_agent run --config config/demo.toml
python -m fitech_agent serve --config config/demo.toml
```

然后打开：

```text
http://127.0.0.1:8010
```

## 9. 常见问题

### 9.1 为什么没有 PDF

通常是因为当前环境没有可用的 PDF 渲染依赖。Markdown 仍然会正常输出。

### 9.2 为什么 live 模式没有抓到消息

常见原因：

- 当前网络不可访问 live 来源
- 来源站点限流
- 时间窗内没有符合过滤条件的内容

建议先用 `config/demo.toml` 验证主流程，再切到 `config/example.toml`。

### 9.3 没有模型能运行吗

可以。当前项目支持规则回退，模型主要用于增强，不是主流程硬依赖。
