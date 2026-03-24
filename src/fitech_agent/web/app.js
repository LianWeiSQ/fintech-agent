const VIEW_ORDER = ["overview", "assistant", "sources", "workflow", "report"];

const VIEW_META = {
  overview: {
    icon: "综",
    label: "综合分析",
    eyebrow: "Workbench",
    title: "综合分析",
    subtitle: "发起研究、查看综合判断，并把重点板块、主线、报告预览和来源摘要集中在首页。",
  },
  assistant: {
    icon: "问",
    label: "智能问答",
    eyebrow: "Assistant",
    title: "智能问答",
    subtitle: "支持基于当前研究结果继续追问，也支持围绕系统能力、来源分层和使用方式做通用咨询。",
  },
  sources: {
    icon: "源",
    label: "新闻源",
    eyebrow: "Source Center",
    title: "新闻源",
    subtitle: "单独查看 L1-L3 权威来源分层、来源类别看板和配置目录，不再把完整来源列表堆在首页。",
  },
  workflow: {
    icon: "程",
    label: "研究过程",
    eyebrow: "Workflow",
    title: "研究过程",
    subtitle: "聚焦展示工作流阶段、时间线、事件列表，以及审计与降级说明。",
  },
  report: {
    icon: "报",
    label: "研究报告",
    eyebrow: "Report",
    title: "研究报告",
    subtitle: "集中查看本轮运行的报告状态、Markdown/PDF 输出和研究简报内容。",
  },
};

const ASSISTANT_MODES = [
  { value: "run_context", label: "研究追问", description: "基于当前 run 继续追问主线、风险和资产影响。" },
  { value: "general", label: "通用咨询", description: "只基于本地配置和已知能力回答，不假装有实时行情。" },
];

const SOURCE_LEVEL_OPTIONS = [
  { value: "all", label: "全部层级" },
  { value: "L1", label: "L1" },
  { value: "L2", label: "L2" },
  { value: "L3", label: "L3" },
];

const SOURCE_CLASS_OPTIONS = [
  { value: "all", label: "全部类别" },
  { value: "official", label: "官方锚点" },
  { value: "media", label: "权威媒体" },
  { value: "x_selected", label: "精选 X" },
];

const SOURCE_ACTIVITY_OPTIONS = [
  { value: "active", label: "当前命中" },
  { value: "configured", label: "仅配置" },
  { value: "all", label: "全部" },
];

const LEVEL_ORDER = ["L1", "L2", "L3"];

const WORKFLOW_DETAIL_MAP = {
  ingestion: "正在选择消息源并收集、归一化原始新闻…",
  event_intelligence: "正在聚类新闻、抽取事件并评估可信度…",
  market_reasoning: "正在映射资产影响并整合跨资产观点…",
  audit: "正在生成审计说明和降级痕迹…",
  report: "正在渲染研究报告并检查输出文件状态…",
};

const DEFAULT_ASSISTANT_PROMPTS = {
  general: ["这个系统现在能做什么？", "黄金/白银消息源怎么分层？", "怎么开始一轮贵金属研究分析？"],
  run_context: ["黄金最值得盯的风险变量是什么？", "把当前主线改写成贵金属盘前播报口径。", "只看黄金和白银还需要盯什么？"],
};

const state = {
  bootstrap: null,
  latestRun: null,
  activeView: "overview",
  assistantMode: "run_context",
  messages: {
    general: [],
    runContext: [],
  },
  pendingAction: null,
  sidebarOpen: false,
  workflowTimer: null,
  workflowPreview: null,
  sourceFilters: {
    level: "all",
    sourceClass: "all",
    activity: "configured",
  },
  researchForm: {
    prompt: "",
    mode: "full_report",
    lookbackHours: 18,
    scopes: [],
  },
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  initialize().catch((error) => {
    renderFatalError(error);
  });
});

function cacheElements() {
  Object.assign(els, {
    sidebar: document.getElementById("sidebar"),
    sidebarBackdrop: document.getElementById("sidebarBackdrop"),
    sidebarToggleButton: document.getElementById("sidebarToggleButton"),
    navList: document.getElementById("navList"),
    viewEyebrow: document.getElementById("viewEyebrow"),
    viewTitle: document.getElementById("viewTitle"),
    viewSubtitle: document.getElementById("viewSubtitle"),
    modelBadge: document.getElementById("modelBadge"),
    runWindow: document.getElementById("runWindow"),
    runStatusBadge: document.getElementById("runStatusBadge"),
    runBadge: document.getElementById("runBadge"),
    promptInput: document.getElementById("promptInput"),
    quickPrompts: document.getElementById("quickPrompts"),
    modeSwitch: document.getElementById("modeSwitch"),
    lookbackHours: document.getElementById("lookbackHours"),
    scopeChips: document.getElementById("scopeChips"),
    runResearchButton: document.getElementById("runResearchButton"),
    signalCards: document.getElementById("signalCards"),
    heroScore: document.getElementById("heroScore"),
    heroTitle: document.getElementById("heroTitle"),
    heroLabel: document.getElementById("heroLabel"),
    heroSummary: document.getElementById("heroSummary"),
    overviewBoards: document.getElementById("overviewBoards"),
    overviewWatchlist: document.getElementById("overviewWatchlist"),
    marketTape: document.getElementById("marketTape"),
    reportPreview: document.getElementById("reportPreview"),
    overviewSourceSummary: document.getElementById("overviewSourceSummary"),
    assistantModeSwitch: document.getElementById("assistantModeSwitch"),
    assistantContext: document.getElementById("assistantContext"),
    assistantPrompts: document.getElementById("assistantPrompts"),
    assistantThread: document.getElementById("assistantThread"),
    assistantInput: document.getElementById("assistantInput"),
    assistantSendButton: document.getElementById("assistantSendButton"),
    levelFilters: document.getElementById("levelFilters"),
    classFilters: document.getElementById("classFilters"),
    activityFilters: document.getElementById("activityFilters"),
    sourceMixCards: document.getElementById("sourceMixCards"),
    sourceLevelBoards: document.getElementById("sourceLevelBoards"),
    sourceClassBoards: document.getElementById("sourceClassBoards"),
    sourceCatalog: document.getElementById("sourceCatalog"),
    workflowList: document.getElementById("workflowList"),
    auditPanel: document.getElementById("auditPanel"),
    timelineList: document.getElementById("timelineList"),
    eventList: document.getElementById("eventList"),
    reportStatus: document.getElementById("reportStatus"),
    reportLinks: document.getElementById("reportLinks"),
    reportSections: document.getElementById("reportSections"),
    views: Array.from(document.querySelectorAll(".view")),
  });
}

function bindEvents() {
  els.sidebarToggleButton.addEventListener("click", () => {
    state.sidebarOpen = true;
    renderSidebarState();
  });
  els.sidebarBackdrop.addEventListener("click", () => {
    state.sidebarOpen = false;
    renderSidebarState();
  });

  els.promptInput.addEventListener("input", (event) => {
    state.researchForm.prompt = event.target.value;
  });
  els.lookbackHours.addEventListener("input", (event) => {
    state.researchForm.lookbackHours = Number(event.target.value || 18);
  });
  els.runResearchButton.addEventListener("click", handleRunResearch);

  els.assistantSendButton.addEventListener("click", handleAssistantSend);
  els.assistantInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      handleAssistantSend();
    }
  });

  window.addEventListener("hashchange", () => {
    applyHashView(false);
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 980 && state.sidebarOpen) {
      state.sidebarOpen = false;
      renderSidebarState();
    }
  });
}

async function initialize() {
  state.bootstrap = await fetchJson("/api/bootstrap");
  state.researchForm = {
    prompt: state.bootstrap.quickPrompts?.[0] || "",
    mode: state.bootstrap.defaults?.mode || "full_report",
    lookbackHours: state.bootstrap.defaults?.lookbackHours || 18,
    scopes: (state.bootstrap.scopes || []).map((scope) => scope.value),
  };
  state.messages.general = [
    makeMessage({
      role: "assistant",
      label: "通用咨询",
      text: "这里可以咨询系统能力、贵金属研究范围、权威来源分层和使用方式。回答只基于本地配置与已知能力，不会假装有实时行情。",
      nextPrompts: DEFAULT_ASSISTANT_PROMPTS.general,
    }),
  ];
  state.messages.runContext = [];

  applyHashView(true);
  render();
}

function render() {
  renderSidebar();
  renderSidebarState();
  renderHeader();
  renderViewVisibility();
  renderOverview();
  renderAssistant();
  renderSources();
  renderWorkflowView();
  renderReportView();
}

function renderFatalError(error) {
  const message = error instanceof Error ? error.message : String(error);
  document.body.innerHTML = `
    <main class="fatal-shell">
      <section class="fatal-card">
        <div class="fatal-kicker">Dashboard Error</div>
        <h1>初始化失败</h1>
        <p>${escapeHtml(message)}</p>
      </section>
    </main>
  `;
}

function renderSidebar() {
  els.navList.innerHTML = "";
  VIEW_ORDER.forEach((viewId) => {
    const meta = VIEW_META[viewId];
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-item${state.activeView === viewId ? " active" : ""}`;
    button.innerHTML = `
      <span class="nav-icon">${escapeHtml(meta.icon)}</span>
      <span class="nav-copy">
        <strong>${escapeHtml(meta.label)}</strong>
        <span>${escapeHtml(meta.subtitle)}</span>
      </span>
    `;
    button.addEventListener("click", () => setActiveView(viewId, true));
    els.navList.appendChild(button);
  });
}

function renderSidebarState() {
  els.sidebar.classList.toggle("is-open", state.sidebarOpen);
  els.sidebarBackdrop.classList.toggle("is-visible", state.sidebarOpen);
}

function renderHeader() {
  const meta = VIEW_META[state.activeView];
  els.viewEyebrow.textContent = meta.eyebrow;
  els.viewTitle.textContent = meta.title;
  els.viewSubtitle.textContent = meta.subtitle;
  els.modelBadge.textContent = formatModelBadge();
  els.runWindow.textContent = state.latestRun ? `窗口 ${formatWindow(state.latestRun.meta?.window)}` : "等待运行";
  els.runStatusBadge.textContent = formatRunStatus();
  els.runBadge.textContent = formatOverviewBadge();
  els.runBadge.classList.toggle("accent", Boolean(state.latestRun));
  els.runResearchButton.disabled = state.pendingAction === "run";
  els.runResearchButton.textContent = state.pendingAction === "run" ? "分析中…" : "开始分析";
}

function renderViewVisibility() {
  els.views.forEach((view) => {
    view.classList.toggle("is-active", view.dataset.view === state.activeView);
  });
}

function renderOverview() {
  renderQuickPrompts();
  renderModeSwitch();
  renderScopeChips();

  els.promptInput.placeholder = state.bootstrap?.promptPlaceholder || els.promptInput.placeholder;
  if (els.promptInput.value !== state.researchForm.prompt) {
    els.promptInput.value = state.researchForm.prompt;
  }
  if (Number(els.lookbackHours.value || 0) !== Number(state.researchForm.lookbackHours)) {
    els.lookbackHours.value = String(state.researchForm.lookbackHours);
  }

  const signalCards = state.latestRun?.signalCards || buildBootstrapSignalCards();
  els.signalCards.innerHTML = signalCards.length ? signalCards.map(renderSignalCard).join("") : renderEmptyState("等待运行后生成指标条。");

  const hero = state.latestRun?.hero || state.bootstrap?.hero || {};
  els.heroScore.textContent = String(hero.score ?? 52);
  els.heroTitle.textContent = hero.label || "等待运行";
  els.heroLabel.textContent = hero.dominantDomain || hero.label || "等待任务";
  els.heroSummary.textContent = hero.summary || "运行后展示综合判断、主线和来源摘要。";

  renderOverviewBoards();
  renderTagCollection(els.overviewWatchlist, state.latestRun?.watchlist || [], "运行后这里会出现重点观察变量。");
  renderTape(els.marketTape, state.latestRun?.marketTape || [], "运行后这里会汇总事件标题、watchlist 和降级原因。");
  renderReportPreview();
  renderOverviewSourceSummary();
}

function renderQuickPrompts() {
  els.quickPrompts.innerHTML = "";
  (state.bootstrap?.quickPrompts || []).forEach((prompt) => {
    const button = createPillButton("quick-prompt", prompt, () => {
      state.researchForm.prompt = prompt;
      els.promptInput.value = prompt;
    });
    els.quickPrompts.appendChild(button);
  });
}

function renderModeSwitch() {
  els.modeSwitch.innerHTML = "";
  (state.bootstrap?.modes || []).forEach((mode) => {
    const active = state.researchForm.mode === mode.value;
    const button = createPillButton(`segment-btn${active ? " active" : ""}`, mode.label, () => {
      state.researchForm.mode = mode.value;
      renderHeader();
      renderModeSwitch();
    });
    els.modeSwitch.appendChild(button);
  });
}

function renderScopeChips() {
  els.scopeChips.innerHTML = "";
  (state.bootstrap?.scopes || []).forEach((scope) => {
    const active = state.researchForm.scopes.includes(scope.value);
    const button = createPillButton(`chip${active ? " active" : ""}`, scope.label, () => {
      if (active && state.researchForm.scopes.length > 1) {
        state.researchForm.scopes = state.researchForm.scopes.filter((value) => value !== scope.value);
      } else if (!active) {
        state.researchForm.scopes = [...state.researchForm.scopes, scope.value];
      }
      renderScopeChips();
    });
    button.title = scope.description || "";
    els.scopeChips.appendChild(button);
  });
}

function renderOverviewBoards() {
  const boards = state.latestRun?.domainBoards || [];
  if (!boards.length) {
    els.overviewBoards.innerHTML = renderEmptyState("运行后这里会把现有 domain boards 重组为重点板块卡片。");
    return;
  }

  els.overviewBoards.innerHTML = boards
    .map((board) => {
      const leadItem = board.items?.[0];
      const itemsHtml = (board.items || [])
        .slice(0, 3)
        .map((item) => {
          return `
            <div class="board-line">
              <span class="tone-pill ${escapeHtml(item.tone || "neutral")}">${escapeHtml(item.direction || "观察")}</span>
              <div>
                <strong>${escapeHtml(item.title || board.label || "关注点")}</strong>
                <div class="line-copy">${escapeHtml(item.detail || "")}</div>
              </div>
            </div>
          `;
        })
        .join("");
      return `
        <article class="board-card ${escapeHtml(leadItem?.tone || "neutral")}">
          <div class="board-head">
            <div>
              <h3>${escapeHtml(board.label || "板块")}</h3>
              <p>${escapeHtml(board.headline || board.focus || "")}</p>
            </div>
            <span class="board-score">${escapeHtml(String(leadItem?.confidence ?? 42))}</span>
          </div>
          <div class="board-lines">${itemsHtml}</div>
          <div class="board-foot">继续关注：${escapeHtml(leadItem?.watch || board.focus || "等待更多证据")}</div>
        </article>
      `;
    })
    .join("");
}

function renderReportPreview() {
  const sections = state.latestRun?.reportSections || [];
  if (!sections.length) {
    els.reportPreview.innerHTML = renderEmptyState("运行后这里会预览报告章节。");
    return;
  }

  els.reportPreview.innerHTML = sections
    .map((section) => renderStackItem(section.title, (section.items || []).slice(0, 2).join("；") || "暂无内容"))
    .join("");
}

function renderOverviewSourceSummary() {
  const sourceMix = state.latestRun?.sourceMix || state.bootstrap?.sourceMix;
  const lines = [];

  (sourceMix?.levels || []).forEach((level) => {
    lines.push({
      title: level.label,
      copy: sourceMix.mode === "active" ? `${level.itemCount || 0} 条消息 / ${level.sourceCount || 0} 个命中来源` : `${level.sourceCount || 0} 个配置来源`,
    });
  });
  (sourceMix?.topSources || []).slice(0, 2).forEach((source) => {
    const copy = source.latestTitle ? `${source.sourceClassLabel} · ${source.latestTitle}` : `${source.sourceClassLabel} · Trust ${source.trustScore || 0}%`;
    lines.push({ title: source.name, copy });
  });

  if (!lines.length) {
    els.overviewSourceSummary.innerHTML = renderEmptyState("暂无来源摘要。");
    return;
  }

  els.overviewSourceSummary.innerHTML = lines.slice(0, 5).map((item) => renderStackItem(item.title, item.copy)).join("");
}

function renderAssistant() {
  renderAssistantModeSwitch();
  renderAssistantContext();
  renderAssistantPrompts();
  renderAssistantThread();

  const disabled = state.pendingAction === "chat" || (state.assistantMode === "run_context" && !state.latestRun);
  els.assistantSendButton.disabled = disabled;
  els.assistantSendButton.textContent = state.pendingAction === "chat" ? "发送中…" : "发送";
  els.assistantInput.placeholder = getAssistantPlaceholder();
}

function renderAssistantModeSwitch() {
  els.assistantModeSwitch.innerHTML = "";
  ASSISTANT_MODES.forEach((mode) => {
    const active = state.assistantMode === mode.value;
    const button = createPillButton(`segment-btn${active ? " active" : ""}`, mode.label, () => {
      state.assistantMode = mode.value;
      renderAssistant();
    });
    button.title = mode.description;
    els.assistantModeSwitch.appendChild(button);
  });
}

function renderAssistantContext() {
  if (state.assistantMode === "general") {
    const modelText = state.bootstrap?.model?.available ? "可选模型增强已接入" : "当前走规则回退";
    const sourceCount = state.bootstrap?.sourceCatalog?.totalSources || 0;
    const scopeCount = state.bootstrap?.scopes?.length || 0;
    els.assistantContext.innerHTML = `
      <div class="context-title">通用咨询</div>
      <p>你可以询问系统能力、贵金属研究流程、权威来源分层、命令入口和使用建议。回答只基于本地配置与已知能力。</p>
      <div class="context-meta-grid">
        <span>消息源 ${escapeHtml(String(sourceCount))} 个</span>
        <span>Scopes ${escapeHtml(String(scopeCount))} 个</span>
        <span>${escapeHtml(modelText)}</span>
      </div>
    `;
    return;
  }

  if (!state.latestRun) {
    els.assistantContext.innerHTML = `
      <div class="context-title">研究追问</div>
      <p>当前还没有可追问的 run。先到综合分析页发起一轮研究，再回来围绕主线、风险和资产影响继续追问。</p>
      <a class="inline-link" href="#overview">先去综合分析发起研究</a>
    `;
    return;
  }

  const meta = state.latestRun.meta || {};
  const degraded = meta.degradedReasons || [];
  els.assistantContext.innerHTML = `
    <div class="context-title">Run #${escapeHtml(String(meta.runId || "--"))} · ${escapeHtml(meta.modeLabel || meta.mode || "--")}</div>
    <p>当前对话会复用本轮研究上下文，只回答这轮运行中已经生成的判断、事件、来源分层和审计信息。</p>
    <div class="context-meta-grid">
      <span>${escapeHtml(formatWindow(meta.window))}</span>
      <span>${escapeHtml(formatScopeSummary(meta.scopes || []))}</span>
      <span>${escapeHtml(formatSourceSummary(meta.sources || []))}</span>
    </div>
    ${
      degraded.length
        ? `<div class="context-note">降级说明：${escapeHtml(degraded.join("；"))}</div>`
        : `<div class="context-note success">本轮无显式降级说明。</div>`
    }
  `;
}

function renderAssistantPrompts() {
  els.assistantPrompts.innerHTML = "";
  const thread = getCurrentThread();
  const latestAssistant = [...thread].reverse().find((message) => message.role === "assistant");
  const prompts = latestAssistant?.nextPrompts?.length ? latestAssistant.nextPrompts : DEFAULT_ASSISTANT_PROMPTS[state.assistantMode];

  prompts.forEach((prompt) => {
    const button = createPillButton("quick-prompt", prompt, () => {
      els.assistantInput.value = prompt;
      els.assistantInput.focus();
    });
    els.assistantPrompts.appendChild(button);
  });
}

function renderAssistantThread() {
  const thread = getCurrentThread();
  if (!thread.length) {
    const emptyText = state.assistantMode === "general" ? "可以直接问系统能力、来源分层、运行模式和使用方法。" : "发起研究后，这里会保留独立的研究追问线程。";
    els.assistantThread.innerHTML = renderEmptyState(emptyText, true);
    return;
  }

  els.assistantThread.innerHTML = thread.map(renderMessage).join("");
  els.assistantThread.scrollTop = els.assistantThread.scrollHeight;
}

function renderSources() {
  renderSourceFilters();

  const filteredSources = getFilteredSources();
  renderSourceMixCards(filteredSources);
  renderSourceLevelBoards(filteredSources);
  renderSourceClassBoards();
  renderSourceCatalog(filteredSources);
}

function renderSourceFilters() {
  renderFilterRow(els.levelFilters, SOURCE_LEVEL_OPTIONS, state.sourceFilters.level, (value) => {
    state.sourceFilters.level = value;
    renderSources();
  });
  renderFilterRow(els.classFilters, SOURCE_CLASS_OPTIONS, state.sourceFilters.sourceClass, (value) => {
    state.sourceFilters.sourceClass = value;
    renderSources();
  });
  renderFilterRow(els.activityFilters, SOURCE_ACTIVITY_OPTIONS, state.sourceFilters.activity, (value) => {
    state.sourceFilters.activity = value;
    renderSources();
  });
}

function renderSourceMixCards(entries) {
  const grouped = groupSourcesByLevel(entries);
  const cards = LEVEL_ORDER
    .filter((level) => state.sourceFilters.level === "all" || state.sourceFilters.level === level)
    .map((level) => {
      const items = grouped[level] || [];
      const levelMeta = findLevelMeta(level);
      return {
        level,
        label: levelMeta.label || level,
        description: levelMeta.description || "",
        sourceCount: items.length,
        itemCount: items.reduce((sum, entry) => sum + Number(entry.itemCount || 0), 0),
        activeCount: items.filter((entry) => entry.active).length,
      };
    })
    .filter((card) => card.sourceCount > 0 || state.sourceFilters.activity !== "active");

  if (!cards.length) {
    els.sourceMixCards.innerHTML = renderEmptyState("当前筛选条件下没有来源。");
    return;
  }

  els.sourceMixCards.innerHTML = cards
    .map((card) => {
      const meta = state.sourceFilters.activity === "configured" || !state.latestRun ? `${card.sourceCount} 个配置来源` : `${card.itemCount} 条消息 / ${card.activeCount} 个命中来源`;
      return `
        <article class="source-mix-card">
          <div class="source-mix-top">
            <strong>${escapeHtml(card.level)}</strong>
            <span>${escapeHtml(card.label)}</span>
          </div>
          <div class="source-mix-count">${escapeHtml(String(card.itemCount || card.sourceCount))}</div>
          <div class="source-mix-meta">${escapeHtml(meta)}</div>
          <div class="source-mix-desc">${escapeHtml(card.description)}</div>
        </article>
      `;
    })
    .join("");
}

function renderSourceLevelBoards(entries) {
  const grouped = groupSourcesByLevel(entries);
  const sections = LEVEL_ORDER
    .filter((level) => state.sourceFilters.level === "all" || state.sourceFilters.level === level)
    .map((level) => {
      const items = grouped[level] || [];
      if (!items.length) {
        return "";
      }
      const meta = findLevelMeta(level);
      const rows = items
        .map((entry) => {
          const latest = entry.latestTitle || "当前没有命中消息，保留为配置来源。";
          const details = entry.active ? `${entry.sourceClassLabel} · ${entry.itemCount} 条 · Trust ${entry.trustScore}%` : `${entry.sourceClassLabel} · 配置来源 · Trust ${entry.trustScore}%`;
          return `
            <article class="stack-item">
              <div class="stack-head">
                <strong>${escapeHtml(entry.name)}</strong>
                <span class="mini-pill">${escapeHtml(entry.sourceClassLabel)}</span>
              </div>
              <div class="stack-meta">${escapeHtml(details)}</div>
              <p>${escapeHtml(latest)}</p>
            </article>
          `;
        })
        .join("");
      return `
        <section class="source-level-board">
          <div class="source-level-head">
            <div>
              <strong>${escapeHtml(meta.label || level)}</strong>
              <div class="source-level-meta">${escapeHtml(meta.description || "")}</div>
            </div>
            <span class="source-level-stats">${escapeHtml(String(items.length))} 个来源</span>
          </div>
          <div class="source-entry-list">${rows}</div>
        </section>
      `;
    })
    .filter(Boolean);

  els.sourceLevelBoards.innerHTML = sections.length ? sections.join("") : renderEmptyState("当前筛选条件下没有可展示的来源分层。");
}

function renderSourceClassBoards() {
  const classes = getVisibleSourceClasses();
  if (!classes.length) {
    els.sourceClassBoards.innerHTML = renderEmptyState("当前筛选下没有可展示的来源类别。");
    return;
  }

  els.sourceClassBoards.innerHTML = classes
    .map((group) => {
      const entries = (group.entries || [])
        .map((entry) => {
          const latest = entry.latestTitle || "当前窗口暂无命中内容，保留为配置来源。";
          return `
            <article class="stack-item">
              <div class="stack-head">
                <strong>${escapeHtml(entry.name || entry.label || "来源")}</strong>
                <span class="mini-pill">${escapeHtml(entry.levelLabel || entry.confidenceLabel || group.label)}</span>
              </div>
              <div class="stack-meta">${escapeHtml(`Trust ${entry.trustScore || 0}% · ${entry.itemCount || 0} 条`)}</div>
              <p>${escapeHtml(latest)}</p>
            </article>
          `;
        })
        .join("");

      return `
        <section class="social-panel">
          <div class="social-panel-head">
            <div>
              <strong>${escapeHtml(group.label)}</strong>
              <div class="source-level-meta">${escapeHtml(group.description || "")}</div>
            </div>
            <span class="source-level-stats">${escapeHtml(String(group.entryCount || group.sourceCount || 0))} 个来源</span>
          </div>
          <div class="source-entry-list">
            ${entries || renderEmptyState("当前没有命中来源，展示为配置名单。")}
          </div>
        </section>
      `;
    })
    .join("");
}

function renderSourceCatalog(entries) {
  if (!entries.length) {
    els.sourceCatalog.innerHTML = renderEmptyState("当前筛选条件下没有来源目录。");
    return;
  }

  els.sourceCatalog.innerHTML = entries
    .map((entry) => {
      const summary = entry.active ? `${entry.levelLabel} · ${entry.sourceClassLabel} · ${entry.itemCount} 条消息` : `${entry.levelLabel} · ${entry.sourceClassLabel} · 配置来源`;
      const detail = entry.latestTitle || entry.tags.join(" / ") || "暂无额外说明";
      return renderStackItem(entry.name, detail, summary);
    })
    .join("");
}

function renderWorkflowView() {
  renderWorkflowList();
  renderAuditPanel();
  renderTimeline();
  renderEvents();
}

function renderWorkflowList() {
  const workflow = getVisibleWorkflow();
  if (!workflow.length) {
    els.workflowList.innerHTML = renderEmptyState("运行后这里会展示实际工作流。");
    return;
  }

  els.workflowList.innerHTML = workflow
    .map((step) => {
      return `
        <li class="workflow-item ${escapeHtml(step.status || "idle")}">
          <div class="step-label">${escapeHtml(step.label || step.id || "阶段")}</div>
          <div class="step-detail">${escapeHtml(step.detail || "等待执行")}</div>
        </li>
      `;
    })
    .join("");
}

function renderAuditPanel() {
  const notes = [];

  if (!state.latestRun) {
    els.auditPanel.innerHTML = renderEmptyState("运行后这里会展示 auditNotes 和 degradedReasons。");
    return;
  }

  if (state.latestRun.meta?.mode === "collect_only") {
    notes.push({
      title: "仅采集模式",
      copy: "本轮在 ingestion 后停止，后续 event / reasoning / audit / report 节点以 skipped 展示。",
      meta: "collect_only",
    });
  }
  (state.latestRun.auditNotes || []).forEach((note, index) => {
    notes.push({ title: `Audit Note ${index + 1}`, copy: note, meta: "审计链" });
  });
  (state.latestRun.meta?.degradedReasons || []).forEach((reason, index) => {
    notes.push({ title: `Degraded Reason ${index + 1}`, copy: reason, meta: "降级说明" });
  });

  els.auditPanel.innerHTML = notes.length ? notes.map((item) => renderStackItem(item.title, item.copy, item.meta)).join("") : renderEmptyState("本轮没有额外的审计或降级说明。");
}

function renderTimeline() {
  const timeline = state.latestRun?.timeline || [];
  if (!timeline.length) {
    const text = state.latestRun?.meta?.mode === "collect_only" ? "仅采集模式下仍可看到采集到的时间线；当前没有命中样本。" : "运行后这里会展示原始新闻时间线。";
    els.timelineList.innerHTML = renderEmptyState(text);
    return;
  }

  els.timelineList.innerHTML = timeline
    .map((item) => renderStackItem(item.title || item.source || "时间线", item.summary || "暂无摘要", `${formatTime(item.time)} · ${item.source || "来源未知"}`))
    .join("");
}

function renderEvents() {
  const events = state.latestRun?.events || [];
  if (!events.length) {
    const text = state.latestRun?.meta?.mode === "collect_only" ? "collect_only 模式不会继续生成 canonical events。" : "运行后这里会展示事件抽取结果。";
    els.eventList.innerHTML = renderEmptyState(text);
    return;
  }

  els.eventList.innerHTML = events
    .map((event) => {
      const evidence = (event.evidence || []).join(" / ") || "暂无证据来源";
      return renderStackItem(event.title || "事件", event.summary || "暂无摘要", `${event.eventType || "事件"} · ${event.bias || "未标注"} · ${evidence}`);
    })
    .join("");
}

function renderReportView() {
  renderReportStatus();
  renderReportLinks();
  renderReportSections();
}

function renderReportStatus() {
  if (!state.latestRun) {
    els.reportStatus.innerHTML = renderEmptyState("发起研究后，这里会展示 run 元信息和输出状态。");
    return;
  }

  const meta = state.latestRun.meta || {};
  const rows = [
    { title: "运行编号", copy: `Run #${meta.runId || "--"} · ${meta.modeLabel || meta.mode || "--"}`, meta: formatWindow(meta.window) },
    { title: "输出状态", copy: meta.markdownPath ? "Markdown 已生成" : "Markdown 未生成", meta: meta.pdfPath ? "PDF 已生成" : "PDF 暂不可用" },
    { title: "范围摘要", copy: formatScopeSummary(meta.scopes || []), meta: formatSourceSummary(meta.sources || []) },
  ];

  (meta.degradedReasons || []).forEach((reason, index) => {
    rows.push({ title: `降级说明 ${index + 1}`, copy: reason, meta: "runtime" });
  });

  if (meta.mode === "collect_only") {
    rows.push({ title: "报告生成", copy: "本轮为仅采集模式，没有生成正式研报。", meta: "collect_only" });
  }

  els.reportStatus.innerHTML = rows.map((item) => renderStackItem(item.title, item.copy, item.meta)).join("");
}

function renderReportLinks() {
  if (!state.latestRun) {
    els.reportLinks.innerHTML = renderEmptyState("运行后这里会展示 Markdown / PDF 文件入口。");
    return;
  }

  const meta = state.latestRun.meta || {};
  const links = [];

  if (meta.markdownPath) {
    links.push(renderFileLink("Markdown 报告", meta.markdownPath, "md"));
  } else {
    links.push(renderStackItem("Markdown 报告", "当前没有 Markdown 输出。"));
  }

  if (meta.pdfPath) {
    links.push(renderFileLink("PDF 报告", meta.pdfPath, "pdf"));
  } else if (meta.mode === "collect_only") {
    links.push(renderStackItem("PDF 报告", "collect_only 模式不会生成 PDF。"));
  } else {
    links.push(renderStackItem("PDF 报告", "当前没有 PDF 输出，通常是未安装 ReportLab 或被降级跳过。"));
  }

  els.reportLinks.innerHTML = links.join("");
}

function renderReportSections() {
  if (!state.latestRun) {
    els.reportSections.innerHTML = renderEmptyState("运行后这里会按章节展示研究报告内容。");
    return;
  }

  const sections = state.latestRun.reportSections || [];
  if (!sections.length) {
    els.reportSections.innerHTML = renderEmptyState("当前没有可展示的报告章节。");
    return;
  }

  els.reportSections.innerHTML = sections
    .map((section) => {
      const items = (section.items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      return `
        <article class="report-section-card">
          <div class="stack-head">
            <strong>${escapeHtml(section.title || "章节")}</strong>
          </div>
          <ul class="report-section-list">${items || "<li>暂无内容</li>"}</ul>
        </article>
      `;
    })
    .join("");
}

async function handleRunResearch() {
  if (state.pendingAction) {
    return;
  }

  state.researchForm.prompt = els.promptInput.value.trim();
  state.researchForm.lookbackHours = Number(els.lookbackHours.value || state.researchForm.lookbackHours || 18);

  state.pendingAction = "run";
  startWorkflowSimulation();
  render();

  try {
    const result = await fetchJson("/api/research/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: state.researchForm.prompt,
        mode: state.researchForm.mode,
        lookbackHours: state.researchForm.lookbackHours,
        scopes: state.researchForm.scopes,
      }),
    });

    stopWorkflowSimulation(result.workflow || null);
    state.latestRun = result;
    state.sourceFilters.activity = "active";
    seedRunContextThread(result);
    render();
  } catch (error) {
    stopWorkflowSimulation(buildFailedWorkflow(error));
    state.messages.runContext = [
      makeMessage({
        role: "system",
        label: "运行失败",
        text: `分析失败：${error.message}`,
      }),
    ];
    render();
  } finally {
    state.pendingAction = null;
    renderHeader();
    renderWorkflowView();
    renderAssistant();
  }
}

async function handleAssistantSend() {
  if (state.pendingAction === "chat") {
    return;
  }

  const question = els.assistantInput.value.trim();
  if (!question) {
    return;
  }

  if (state.assistantMode === "run_context" && !state.latestRun) {
    renderAssistant();
    return;
  }

  const threadKey = getCurrentThreadKey();
  pushMessage(
    threadKey,
    makeMessage({
      role: "user",
      label: "你",
      text: question,
    })
  );
  els.assistantInput.value = "";
  state.pendingAction = "chat";
  renderAssistant();

  try {
    const payload = {
      question,
      mode: state.assistantMode,
    };
    if (state.assistantMode === "run_context") {
      payload.runId = state.latestRun?.meta?.runId;
    }
    const result = await fetchJson("/api/research/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    pushMessage(
      threadKey,
      makeMessage({
        role: "assistant",
        label: result.mode === "model" ? "模型回答" : state.assistantMode === "general" ? "通用回答" : "研究追问",
        text: result.answer || "暂无回答。",
        citations: result.citations || [],
        nextPrompts: result.nextPrompts || [],
      })
    );
  } catch (error) {
    pushMessage(
      threadKey,
      makeMessage({
        role: "system",
        label: "错误",
        text: `发送失败：${error.message}`,
      })
    );
  } finally {
    state.pendingAction = null;
    renderAssistant();
  }
}

function startWorkflowSimulation() {
  stopWorkflowSimulation(null, false);
  const baseWorkflow = (state.bootstrap?.workflow || []).map((step) => ({
    ...step,
    status: "idle",
    detail: WORKFLOW_DETAIL_MAP[step.id] || step.detail || "等待执行",
  }));

  let currentIndex = 0;
  state.workflowPreview = baseWorkflow.map((step, index) => ({
    ...step,
    status: index === 0 ? "running" : "idle",
  }));

  state.workflowTimer = window.setInterval(() => {
    currentIndex = (currentIndex + 1) % Math.max(baseWorkflow.length, 1);
    state.workflowPreview = baseWorkflow.map((step, index) => {
      if (index < currentIndex) {
        return {
          ...step,
          status: "completed",
          detail: `${WORKFLOW_DETAIL_MAP[step.id] || step.detail || "已完成"} 已完成`,
        };
      }
      if (index === currentIndex) {
        return {
          ...step,
          status: "running",
          detail: WORKFLOW_DETAIL_MAP[step.id] || step.detail || "执行中",
        };
      }
      return {
        ...step,
        status: "idle",
        detail: WORKFLOW_DETAIL_MAP[step.id] || step.detail || "等待执行",
      };
    });
    renderWorkflowView();
  }, 900);
}

function stopWorkflowSimulation(workflow, shouldRender = true) {
  if (state.workflowTimer) {
    window.clearInterval(state.workflowTimer);
    state.workflowTimer = null;
  }
  state.workflowPreview = workflow;
  if (shouldRender) {
    renderWorkflowView();
  }
}

function buildFailedWorkflow(error) {
  return (state.bootstrap?.workflow || []).map((step, index) => ({
    ...step,
    status: index === 0 ? "error" : "idle",
    detail: index === 0 ? `运行失败：${error.message}` : "未执行",
  }));
}

function seedRunContextThread(result) {
  const meta = result.meta || {};
  state.messages.runContext = [
    makeMessage({
      role: "system",
      label: "研究上下文",
      text: `已载入 Run #${meta.runId || "--"} · ${meta.modeLabel || meta.mode || "--"} · ${formatWindow(meta.window)}。`,
    }),
    makeMessage({
      role: "assistant",
      label: result.assistantOpening?.mode === "model" ? "模型首答" : "规则首答",
      text: result.assistantOpening?.text || "本轮研究已完成，你可以继续追问。",
      nextPrompts: DEFAULT_ASSISTANT_PROMPTS.run_context,
    }),
  ];
}

function renderFilterRow(container, options, activeValue, onSelect) {
  container.innerHTML = "";
  options.forEach((option) => {
    const active = option.value === activeValue;
    const button = createPillButton(`filter-chip${active ? " active" : ""}`, option.label, () => onSelect(option.value));
    container.appendChild(button);
  });
}

function getVisibleWorkflow() {
  if (state.pendingAction === "run" && state.workflowPreview?.length) {
    return state.workflowPreview;
  }
  return state.latestRun?.workflow || state.bootstrap?.workflow || [];
}

function getCurrentThreadKey() {
  return state.assistantMode === "general" ? "general" : "runContext";
}

function getCurrentThread() {
  return state.messages[getCurrentThreadKey()] || [];
}

function pushMessage(threadKey, message) {
  const thread = state.messages[threadKey] || [];
  thread.push(message);
  state.messages[threadKey] = thread;
}

function makeMessage({ role, label, text, citations = [], nextPrompts = [] }) {
  return {
    role,
    label,
    text,
    citations,
    nextPrompts,
  };
}

function renderMessage(message) {
  const citations = (message.citations || []).map((citation) => `<li>${escapeHtml(citation.title || "引用")} · ${escapeHtml(citation.source || "")}</li>`).join("");
  return `
    <article class="message ${escapeHtml(message.role || "assistant")}">
      <div class="message-bubble">
        ${message.label ? `<div class="message-meta">${escapeHtml(message.label)}</div>` : ""}
        <div class="message-text">${formatParagraphs(message.text || "")}</div>
        ${citations ? `<ul class="citation-list">${citations}</ul>` : ""}
      </div>
    </article>
  `;
}

function buildBootstrapSignalCards() {
  const sourceCount = state.bootstrap?.sourceCatalog?.totalSources || 0;
  const modeCount = state.bootstrap?.modes?.length || 0;
  const scopeCount = state.bootstrap?.scopes?.length || 0;
  const model = state.bootstrap?.model || {};
  return [
    { title: "已配置消息源", value: String(sourceCount), detail: "本地 source catalog", tone: "accent" },
    { title: "运行模式", value: `${modeCount} 种`, detail: "完整研报 / 仅采集", tone: "neutral" },
    { title: "覆盖范围", value: `${scopeCount} 个`, detail: "跨资产研究 scope", tone: "neutral" },
    { title: "模型状态", value: model.available ? "已接入" : "规则回退", detail: model.resolvedModel || "未配置模型", tone: model.available ? "positive" : "warning" },
  ];
}

function renderSignalCard(card) {
  return `
    <article class="signal-card ${escapeHtml(card.tone || "neutral")}">
      <div class="signal-title">${escapeHtml(card.title || "指标")}</div>
      <div class="signal-value">${escapeHtml(String(card.value ?? "--"))}</div>
      <div class="signal-detail">${escapeHtml(card.detail || "")}</div>
    </article>
  `;
}

function renderTagCollection(container, items, emptyText) {
  if (!items.length) {
    container.innerHTML = renderEmptyState(emptyText);
    return;
  }
  container.innerHTML = items.map((item) => `<span class="watch-item">${escapeHtml(item)}</span>`).join("");
}

function renderTape(container, items, emptyText) {
  if (!items.length) {
    container.innerHTML = renderEmptyState(emptyText);
    return;
  }
  container.innerHTML = items.map((item) => `<span class="tape-chip">${escapeHtml(item)}</span>`).join("");
}

function renderStackItem(title, copy, meta = "") {
  return `
    <article class="stack-item">
      <div class="stack-head">
        <strong>${escapeHtml(title || "条目")}</strong>
        ${meta ? `<span class="stack-meta">${escapeHtml(meta)}</span>` : ""}
      </div>
      <p>${escapeHtml(copy || "暂无内容")}</p>
    </article>
  `;
}

function renderFileLink(title, path, suffix) {
  const url = `/api/report-file?path=${encodeURIComponent(path)}`;
  return `
    <article class="stack-item">
      <div class="stack-head">
        <strong>${escapeHtml(title)}</strong>
        <span class="stack-meta">${escapeHtml(suffix.toUpperCase())}</span>
      </div>
      <p class="path-copy">${escapeHtml(path)}</p>
      <a class="file-link" href="${url}" target="_blank" rel="noopener noreferrer">打开文件</a>
    </article>
  `;
}

function renderEmptyState(text, tall = false) {
  return `<div class="empty-state${tall ? " tall" : ""}">${escapeHtml(text)}</div>`;
}

function createPillButton(className, text, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = text;
  button.addEventListener("click", onClick);
  return button;
}

function applyHashView(setDefaultWhenMissing) {
  const view = getViewFromHash();
  if (!view && setDefaultWhenMissing) {
    window.location.hash = "#overview";
    state.activeView = "overview";
    return;
  }
  state.activeView = view || "overview";
  render();
}

function setActiveView(viewId, updateHash) {
  state.activeView = viewId;
  state.sidebarOpen = false;
  if (updateHash) {
    window.location.hash = `#${viewId}`;
  } else {
    render();
  }
}

function getViewFromHash() {
  const value = window.location.hash.replace(/^#/, "").trim();
  return VIEW_META[value] ? value : "";
}

function getFilteredSources() {
  const sources = buildSourceUniverse();
  return sources
    .filter((entry) => state.sourceFilters.level === "all" || entry.level === state.sourceFilters.level)
    .filter((entry) => state.sourceFilters.sourceClass === "all" || entry.sourceClass === state.sourceFilters.sourceClass)
    .filter((entry) => {
      if (state.sourceFilters.activity === "all") {
        return true;
      }
      if (state.sourceFilters.activity === "active") {
        return entry.active;
      }
      return !entry.active;
    })
    .sort((left, right) => {
      const levelDelta = LEVEL_ORDER.indexOf(left.level) - LEVEL_ORDER.indexOf(right.level);
      if (levelDelta !== 0) {
        return levelDelta;
      }
      if (left.active !== right.active) {
        return left.active ? -1 : 1;
      }
      if ((right.itemCount || 0) !== (left.itemCount || 0)) {
        return (right.itemCount || 0) - (left.itemCount || 0);
      }
      if ((right.trustScore || 0) !== (left.trustScore || 0)) {
        return (right.trustScore || 0) - (left.trustScore || 0);
      }
      return String(left.name || "").localeCompare(String(right.name || ""), "zh-CN");
    });
}

function buildSourceUniverse() {
  const sourceMap = new Map();
  const configuredLevels = state.bootstrap?.sourceCatalog?.levels || [];
  const runtimeLevels = state.latestRun?.sourceMix?.levels || [];

  configuredLevels.forEach((level) => {
    (level.sources || []).forEach((source) => {
      sourceMap.set(source.name, normalizeSource(source, level.level, level.label, level.description));
    });
  });

  runtimeLevels.forEach((level) => {
    (level.sources || []).forEach((source) => {
      const existing = sourceMap.get(source.name);
      const normalized = normalizeSource(source, level.level, level.label, level.description);
      sourceMap.set(source.name, {
        ...existing,
        ...normalized,
        active: Boolean(source.active) || Number(source.itemCount || 0) > 0,
      });
    });
  });

  return Array.from(sourceMap.values());
}

function normalizeSource(source, fallbackLevel, fallbackLabel, fallbackDescription) {
  const level = source.confidenceLevel || fallbackLevel || "L3";
  return {
    name: source.name,
    label: source.label || source.name,
    level,
    levelLabel: source.confidenceLabel || fallbackLabel || level,
    levelDescription: fallbackDescription || "",
    sourceClass: source.sourceClass || "media",
    sourceClassLabel: source.sourceClassLabel || "权威媒体",
    sourceClassDescription: source.sourceClassDescription || "",
    credibilityNote: source.credibilityNote || "",
    trustScore: Number(source.trustScore || 0),
    itemCount: Number(source.itemCount || 0),
    latestTitle: source.latestTitle || "",
    latestSeen: source.latestSeen || "",
    tags: source.tags || [],
    language: source.language || "",
    kind: source.kind || "",
    tier: source.tier || "",
    active: Boolean(source.active) || Number(source.itemCount || 0) > 0,
  };
}

function groupSourcesByLevel(entries) {
  return entries.reduce((acc, entry) => {
    const level = entry.level || "L3";
    if (!acc[level]) {
      acc[level] = [];
    }
    acc[level].push(entry);
    return acc;
  }, {});
}

function getVisibleSourceClasses() {
  const activeClasses = state.latestRun?.sourceMix?.classes || [];
  const configuredClasses = state.bootstrap?.sourceCatalog?.classes || [];
  const classCodes = ["official", "media", "x_selected"].filter(
    (sourceClass) => state.sourceFilters.sourceClass === "all" || state.sourceFilters.sourceClass === sourceClass
  );

  return classCodes
    .map((classCode) => {
      const active = activeClasses.find((item) => item.sourceClass === classCode);
      const configured = configuredClasses.find((item) => item.sourceClass === classCode);

      if (state.sourceFilters.activity === "configured" || !state.latestRun) {
        return configured || null;
      }

      if (state.sourceFilters.activity === "active") {
        if (!active || !(active.entries?.length || active.itemCount)) {
          return null;
        }
        return active;
      }

      if (active && (active.entries?.length || active.itemCount)) {
        return active;
      }
      return configured || null;
    })
    .filter(Boolean);
}

function findLevelMeta(level) {
  const levels = [...(state.latestRun?.sourceMix?.levels || []), ...(state.bootstrap?.sourceCatalog?.levels || [])];
  return levels.find((item) => item.level === level) || { level, label: level, description: "" };
}

function getAssistantPlaceholder() {
  if (state.assistantMode === "general") {
    return "例如：这个系统支持哪些能力？黄金/白银消息源如何分层？";
  }
  if (!state.latestRun) {
    return "先去综合分析页发起一轮研究";
  }
  return "例如：最值得盯的风险变量是什么？为什么主线落在贵金属？";
}

function formatModelBadge() {
  const model = state.bootstrap?.model || {};
  return model.available ? `模型已接入 · ${model.resolvedModel || model.provider || "LLM"}` : "未接模型，使用规则回退";
}

function formatRunStatus() {
  if (state.pendingAction === "run") {
    return "分析中";
  }
  if (state.latestRun?.meta?.runId) {
    return `运行 #${state.latestRun.meta.runId}`;
  }
  return "待命";
}

function formatOverviewBadge() {
  if (state.pendingAction === "run") {
    return "分析中";
  }
  if (!state.latestRun) {
    return "待命";
  }
  return `${state.latestRun.meta?.modeLabel || state.latestRun.meta?.mode || "已完成"} · #${state.latestRun.meta?.runId || "--"}`;
}

function formatWindow(windowValue) {
  if (!windowValue || !windowValue.start || !windowValue.end) {
    return "等待运行";
  }
  return `${formatTime(windowValue.start)} - ${formatTime(windowValue.end)}`;
}

function formatTime(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatScopeSummary(scopes) {
  if (!scopes.length) {
    return "全部 scope";
  }
  const labels = scopes.map((scope) => {
    const matched = (state.bootstrap?.scopes || []).find((item) => item.value === scope);
    return matched?.label || scope;
  });
  return `Scopes：${labels.join(" / ")}`;
}

function formatSourceSummary(sources) {
  if (!sources.length) {
    return "Sources：全部启用权威来源";
  }
  return `Sources：${sources.slice(0, 3).join(" / ")}${sources.length > 3 ? "…" : ""}`;
}

function formatParagraphs(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch (error) {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }
  return payload;
}
