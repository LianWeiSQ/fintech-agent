const state = {
  bootstrap: null,
  run: null,
  messages: [],
  pending: false,
  workflowTimer: null,
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  initialize().catch((error) => {
    addMessage("system", `初始化失败：${error.message}`, "错误");
    renderChat();
  });
});

function cacheElements() {
  Object.assign(els, {
    pageSubtitle: document.getElementById("pageSubtitle"),
    modelBadge: document.getElementById("modelBadge"),
    runWindow: document.getElementById("runWindow"),
    runBadge: document.getElementById("runBadge"),
    promptInput: document.getElementById("promptInput"),
    quickPrompts: document.getElementById("quickPrompts"),
    modeSwitch: document.getElementById("modeSwitch"),
    lookbackHours: document.getElementById("lookbackHours"),
    scopeChips: document.getElementById("scopeChips"),
    runResearchButton: document.getElementById("runResearchButton"),
    workflowList: document.getElementById("workflowList"),
    chatThread: document.getElementById("chatThread"),
    chatInput: document.getElementById("chatInput"),
    chatSendButton: document.getElementById("chatSendButton"),
    heroLabel: document.getElementById("heroLabel"),
    heroScore: document.getElementById("heroScore"),
    heroTitle: document.getElementById("heroTitle"),
    heroSummary: document.getElementById("heroSummary"),
    focusCards: document.getElementById("focusCards"),
    watchlist: document.getElementById("watchlist"),
    runMeta: document.getElementById("runMeta"),
    sourceMixCards: document.getElementById("sourceMixCards"),
    sourceLevelBoards: document.getElementById("sourceLevelBoards"),
    socialRadar: document.getElementById("socialRadar"),
    sourceCatalog: document.getElementById("sourceCatalog"),
  });
}

function bindEvents() {
  els.runResearchButton.addEventListener("click", handleRunResearch);
  els.chatSendButton.addEventListener("click", handleChatSend);
  els.chatInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      handleChatSend();
    }
  });
}

async function initialize() {
  const bootstrap = await fetchJson("/api/bootstrap");
  state.bootstrap = bootstrap;

  els.promptInput.placeholder = bootstrap.promptPlaceholder || els.promptInput.placeholder;
  els.promptInput.value = bootstrap.quickPrompts?.[0] || "";
  els.lookbackHours.value = bootstrap.defaults?.lookbackHours || 18;

  renderModelBadge(bootstrap.model);
  renderQuickPrompts(bootstrap.quickPrompts || []);
  renderModes(bootstrap.modes || [], bootstrap.defaults?.mode || "full_report");
  renderScopes(bootstrap.scopes || []);
  renderWorkflow(bootstrap.workflow || []);
  renderEmptyFocus();
  renderSourceMix(bootstrap.sourceMix || {});
  renderSocialRadar((bootstrap.sourceMix && bootstrap.sourceMix.channels) || []);
  renderSourceCatalog(bootstrap.sourceCatalog || {});

  addMessage("system", "先描述你的研究问题，再点击开始分析。系统会把执行过程和首轮模型摘要展示在这里。", "提示");
  renderChat();
}

function renderModelBadge(model) {
  const ready = Boolean(model?.available);
  els.modelBadge.textContent = ready ? `模型已接入 · ${model.resolvedModel}` : "未接模型，使用规则回退";
}

function renderQuickPrompts(prompts) {
  els.quickPrompts.innerHTML = "";
  prompts.forEach((prompt) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-prompt";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      els.promptInput.value = prompt;
    });
    els.quickPrompts.appendChild(button);
  });
}

function renderModes(modes, defaultMode) {
  els.modeSwitch.innerHTML = "";
  modes.forEach((mode) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segment-btn${mode.value === defaultMode ? " active" : ""}`;
    button.dataset.value = mode.value;
    button.textContent = mode.label;
    button.addEventListener("click", () => {
      [...els.modeSwitch.querySelectorAll(".segment-btn")].forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
    });
    els.modeSwitch.appendChild(button);
  });
}

function renderScopes(scopes) {
  els.scopeChips.innerHTML = "";
  scopes.forEach((scope) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip active";
    button.dataset.value = scope.value;
    button.textContent = scope.label;
    button.title = scope.description || "";
    button.addEventListener("click", () => {
      button.classList.toggle("active");
    });
    els.scopeChips.appendChild(button);
  });
}

function renderWorkflow(workflow) {
  els.workflowList.innerHTML = "";
  if (!workflow.length) {
    els.workflowList.innerHTML = '<li class="empty-state">暂无执行流程</li>';
    return;
  }
  workflow.forEach((step) => {
    const item = document.createElement("li");
    item.className = `workflow-item ${step.status || "idle"}`;
    item.innerHTML = `
      <div class="step-label">${escapeHtml(step.label || "")}</div>
      <div class="step-detail">${escapeHtml(step.detail || "")}</div>
    `;
    els.workflowList.appendChild(item);
  });
}

function renderEmptyFocus() {
  els.heroScore.textContent = "52";
  els.heroTitle.textContent = "等待运行";
  els.heroLabel.textContent = "等待任务";
  els.heroSummary.textContent = "只显示最值得关注的研究窗口，不再堆叠无关模块。";
  els.focusCards.innerHTML = '<div class="empty-state">运行后展示最值得关注的资产窗口。</div>';
  els.watchlist.innerHTML = '<div class="empty-state">运行后展示盯盘清单。</div>';
  els.runMeta.innerHTML = '<div class="empty-state">运行后展示当前研究窗口、模式和输出状态。</div>';
}

async function handleRunResearch() {
  if (state.pending) {
    return;
  }

  const payload = {
    prompt: els.promptInput.value.trim(),
    mode: getActiveMode(),
    lookbackHours: Number(els.lookbackHours.value || 18),
    scopes: getActiveScopes(),
  };

  setPending(true);
  setRunBadge("运行中");
  startWorkflowSimulation();
  addMessage("system", "开始执行：系统正在采集新闻、抽取事件并汇总成可追问的研究上下文。", "执行中");
  renderChat();

  try {
    const result = await fetchJson("/api/research/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.run = result;
    stopWorkflowSimulation(result.workflow || []);
    renderRunResult(result);
    addMessage(
      "assistant",
      result.assistantOpening?.text || "已完成本轮研究。",
      result.assistantOpening?.mode === "model" ? "模型首轮摘要" : "规则首轮摘要"
    );
    renderChat();
  } catch (error) {
    stopWorkflowSimulation(
      (state.bootstrap?.workflow || []).map((step, index) => ({
        ...step,
        status: index === 0 ? "error" : "idle",
        detail: index === 0 ? error.message : "未执行",
      }))
    );
    setRunBadge("运行失败");
    addMessage("system", `运行失败：${error.message}`, "错误");
    renderChat();
  } finally {
    setPending(false);
  }
}

function renderRunResult(result) {
  renderHero(result.hero || {});
  renderFocusCards(result.domainBoards || []);
  renderWatchlist(result.watchlist || []);
  renderRunMeta(result.meta || {});
  renderWorkflow(result.workflow || []);
  renderSourceMix(result.sourceMix || {});
  renderSocialRadar((result.sourceMix && result.sourceMix.channels) || []);
  renderSourceCatalog(result.sourceCatalog || state.bootstrap?.sourceCatalog || {});
  els.runWindow.textContent = formatWindow(result.meta?.window);
  els.pageSubtitle.textContent = `已完成第 ${result.meta?.runId} 次研究运行，右侧只保留关键关注窗口，左侧可以继续追问模型。`;
  setRunBadge(result.meta?.modeLabel || "已完成");
}

function renderHero(hero) {
  const score = Number(hero.score || 0);
  els.heroScore.textContent = String(score);
  els.heroTitle.textContent = hero.label || "已完成";
  els.heroLabel.textContent = hero.dominantDomain || hero.label || "完成";
  els.heroSummary.textContent = hero.summary || "本轮研究已生成关注窗口。";
}

function renderFocusCards(boards) {
  const ranked = [...boards]
    .map((board) => ({
      board,
      item: board.items?.[0] || null,
    }))
    .filter((entry) => entry.item)
    .sort((left, right) => toneRank(left.item.tone) - toneRank(right.item.tone) || (right.item.confidence || 0) - (left.item.confidence || 0))
    .slice(0, 4);

  if (!ranked.length) {
    els.focusCards.innerHTML = '<div class="empty-state">暂无高优先级关注窗口。</div>';
    return;
  }

  els.focusCards.innerHTML = "";
  ranked.forEach(({ board, item }) => {
    const card = document.createElement("article");
    card.className = `focus-card ${item.tone || "neutral"}`;
    card.innerHTML = `
      <div class="focus-card-head">
        <h4>${escapeHtml(board.label || item.title || "关注窗口")}</h4>
        <span class="tone-pill ${item.tone || "neutral"}">${escapeHtml(item.direction || "观察")}</span>
      </div>
      <p>${escapeHtml(item.detail || board.headline || "")}</p>
      <div class="focus-meta">置信度 ${escapeHtml(String(item.confidence || "--"))}% · ${escapeHtml(item.watch || board.focus || "继续观察")}</div>
    `;
    els.focusCards.appendChild(card);
  });
}

function renderWatchlist(items) {
  if (!items.length) {
    els.watchlist.innerHTML = '<div class="empty-state">暂无盯盘清单。</div>';
    return;
  }
  els.watchlist.innerHTML = "";
  items.slice(0, 8).forEach((item) => {
    const node = document.createElement("span");
    node.className = "watch-item";
    node.textContent = item;
    els.watchlist.appendChild(node);
  });
}

function renderRunMeta(meta) {
  const rows = [
    {
      title: "当前研究窗口",
      value: formatWindow(meta.window),
    },
    {
      title: "运行模式",
      value: meta.modeLabel || meta.mode || "--",
    },
    {
      title: "输出状态",
      value: meta.degradedReasons?.length ? `有降级：${meta.degradedReasons.join(" / ")}` : "正常完成",
    },
  ];

  els.runMeta.innerHTML = "";
  rows.forEach((row) => {
    const node = document.createElement("div");
    node.className = "run-meta-item";
    node.innerHTML = `
      <strong>${escapeHtml(row.title)}</strong>
      <span>${escapeHtml(row.value || "--")}</span>
    `;
    els.runMeta.appendChild(node);
  });
}

function renderSourceMix(sourceMix) {
  const levels = sourceMix.levels || [];
  if (!levels.length) {
    els.sourceMixCards.innerHTML = '<div class="empty-state">暂无 source mix。</div>';
    els.sourceLevelBoards.innerHTML = '<div class="empty-state">暂无分层来源。</div>';
    return;
  }

  els.sourceMixCards.innerHTML = "";
  levels.forEach((level) => {
    const card = document.createElement("article");
    card.className = "source-mix-card";
    card.innerHTML = `
      <div class="source-mix-top">
        <strong>${escapeHtml(level.level || "")}</strong>
        <span>${escapeHtml(level.label || "")}</span>
      </div>
      <div class="source-mix-count">${escapeHtml(String(level.itemCount ?? 0))}</div>
      <div class="source-mix-meta">消息 ${escapeHtml(String(level.itemCount ?? 0))} 条 · 来源 ${escapeHtml(String(level.sourceCount ?? 0))} 个 · 占比 ${escapeHtml(String(level.sharePct ?? 0))}%</div>
      <div class="source-mix-desc">${escapeHtml(level.description || "")}</div>
    `;
    els.sourceMixCards.appendChild(card);
  });

  els.sourceLevelBoards.innerHTML = "";
  levels.forEach((level) => {
    const section = document.createElement("section");
    section.className = "source-level-board";
    const rows = (level.sources || []).map((source) => `
      <div class="source-entry">
        <div class="source-entry-top">
          <strong>${escapeHtml(source.name || "")}</strong>
          <span class="source-pill">${escapeHtml(source.channelLabel || source.channel || "")}</span>
        </div>
        <div class="source-entry-meta">${escapeHtml(source.confidenceLabel || level.label || "")} · Trust ${escapeHtml(String(source.trustScore ?? "--"))}% · ${escapeHtml(String(source.itemCount ?? 0))} 条</div>
        <div class="source-entry-title">${escapeHtml(source.latestTitle || "当前窗口暂无命中，保留为配置来源。").replace(/\n/g, "<br>")}</div>
      </div>
    `).join("");
    section.innerHTML = `
      <div class="source-level-head">
        <div>
          <strong>${escapeHtml(level.label || "")}</strong>
          <div class="source-level-meta">${escapeHtml(level.description || "")}</div>
        </div>
        <span class="source-level-stats">${escapeHtml(String(level.itemCount ?? 0))} 条 / ${escapeHtml(String(level.sourceCount ?? 0))} 源</span>
      </div>
      <div class="source-entry-list">
        ${rows || '<div class="empty-state">该层暂无来源。</div>'}
      </div>
    `;
    els.sourceLevelBoards.appendChild(section);
  });
}

function renderSocialRadar(channels) {
  if (!channels.length) {
    els.socialRadar.innerHTML = '<div class="empty-state">暂无 X / Reddit 热点。</div>';
    return;
  }
  els.socialRadar.innerHTML = "";
  channels.forEach((channel) => {
    const panel = document.createElement("section");
    panel.className = "social-panel";
    const entries = (channel.entries || []).map((entry) => `
      <div class="social-entry">
        <strong>${escapeHtml(entry.name || entry.label || "")}</strong>
        <div class="social-entry-meta">${escapeHtml(entry.levelLabel || entry.confidenceLabel || "")} · ${escapeHtml(String(entry.itemCount ?? 0))} 条 · Trust ${escapeHtml(String(entry.trustScore ?? "--"))}%</div>
        <div class="social-entry-title">${escapeHtml(entry.latestTitle || "当前窗口暂无活跃内容，展示为配置监控名单。").replace(/\n/g, "<br>")}</div>
      </div>
    `).join("");
    const posts = (channel.posts || []).map((post) => `
      <div class="social-post">
        <strong>${escapeHtml(post.author || "")}</strong>
        <div class="social-entry-meta">${escapeHtml(post.levelLabel || "")} · ${escapeHtml(post.source || "")}</div>
        <div class="social-entry-title">${escapeHtml(post.title || "").replace(/\n/g, "<br>")}</div>
      </div>
    `).join("");
    panel.innerHTML = `
      <div class="social-panel-head">
        <div>
          <strong>${escapeHtml(channel.label || "")}</strong>
          <div class="source-level-meta">${escapeHtml(channel.description || "")}</div>
        </div>
        <span class="source-level-stats">${escapeHtml(String(channel.entryCount ?? 0))} 个热点</span>
      </div>
      <div class="social-columns">
        <div class="social-column">
          <div class="social-column-title">热点账号 / 作者</div>
          ${entries || '<div class="empty-state">当前窗口暂无活跃账号，展示配置监控名单。</div>'}
        </div>
        <div class="social-column">
          <div class="social-column-title">热点帖子 / 推文</div>
          ${posts || '<div class="empty-state">当前窗口暂无热点内容。</div>'}
        </div>
      </div>
    `;
    els.socialRadar.appendChild(panel);
  });
}

function renderSourceCatalog(sourceCatalog) {
  const levels = sourceCatalog.levels || [];
  if (!levels.length) {
    els.sourceCatalog.innerHTML = '<div class="empty-state">暂无配置来源目录。</div>';
    return;
  }
  els.sourceCatalog.innerHTML = "";
  levels.forEach((level) => {
    const block = document.createElement("section");
    block.className = "catalog-level";
    const chips = (level.sources || []).map((source) => `
      <span class="catalog-chip">${escapeHtml(source.name || "")}<em>${escapeHtml(source.channelLabel || source.channel || "")}</em></span>
    `).join("");
    block.innerHTML = `
      <div class="source-level-head">
        <div>
          <strong>${escapeHtml(level.label || "")}</strong>
          <div class="source-level-meta">${escapeHtml(level.description || "")}</div>
        </div>
        <span class="source-level-stats">${escapeHtml(String(level.sourceCount ?? 0))} 源</span>
      </div>
      <div class="catalog-chip-list">
        ${chips || '<div class="empty-state">该层暂无配置来源。</div>'}
      </div>
    `;
    els.sourceCatalog.appendChild(block);
  });
}

async function handleChatSend() {
  const question = els.chatInput.value.trim();
  if (!question) {
    return;
  }
  if (!state.run?.chatHandle?.runId) {
    addMessage("system", "请先完成一轮分析，再继续追问模型。", "未就绪");
    renderChat();
    return;
  }

  addMessage("user", question, "追问");
  els.chatInput.value = "";
  renderChat();

  try {
    const response = await fetchJson("/api/research/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        runId: state.run.chatHandle.runId,
      }),
    });
    addMessage("assistant", response.answer, response.mode === "model" ? "模型回答" : "规则回答");
  } catch (error) {
    addMessage("system", `追问失败：${error.message}`, "错误");
  }
  renderChat();
}

function startWorkflowSimulation() {
  const draft = (state.bootstrap?.workflow || []).map((step, index) => ({
    ...step,
    status: index === 0 ? "running" : "idle",
    detail: index === 0 ? "正在整理研究意图" : "等待执行",
  }));
  renderWorkflow(draft);

  let index = 0;
  window.clearInterval(state.workflowTimer);
  state.workflowTimer = window.setInterval(() => {
    if (index >= draft.length - 1) {
      draft[index].status = "running";
      draft[index].detail = "正在等待结果返回";
      renderWorkflow(draft);
      return;
    }
    draft[index].status = "completed";
    index += 1;
    draft[index].status = "running";
    draft[index].detail = `正在执行${draft[index].label}`;
    renderWorkflow(draft);
  }, 850);
}

function stopWorkflowSimulation(workflow) {
  window.clearInterval(state.workflowTimer);
  state.workflowTimer = null;
  renderWorkflow(workflow);
}

function addMessage(role, text, meta = "") {
  state.messages.push({ role, text, meta });
}

function renderChat() {
  els.chatThread.innerHTML = "";
  state.messages.forEach((message) => {
    const node = document.createElement("div");
    node.className = `message ${message.role}`;
    node.innerHTML = `
      <div>
        ${message.meta ? `<div class="message-meta">${escapeHtml(message.meta)}</div>` : ""}
        <div class="message-bubble">${escapeHtml(message.text).replace(/\n/g, "<br>")}</div>
      </div>
    `;
    els.chatThread.appendChild(node);
  });
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}

function setRunBadge(text) {
  els.runBadge.textContent = text;
}

function setPending(pending) {
  state.pending = pending;
  document.body.classList.toggle("is-loading", pending);
  els.runResearchButton.disabled = pending;
  els.chatSendButton.disabled = pending;
}

function getActiveMode() {
  return els.modeSwitch.querySelector(".segment-btn.active")?.dataset.value || state.bootstrap?.defaults?.mode || "full_report";
}

function getActiveScopes() {
  return [...els.scopeChips.querySelectorAll(".chip.active")].map((node) => node.dataset.value).filter(Boolean);
}

function formatWindow(windowData) {
  if (!windowData?.start || !windowData?.end) {
    return "等待运行";
  }
  return `${formatTime(windowData.start)} -> ${formatTime(windowData.end)}`;
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "--";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function toneRank(tone) {
  return {
    positive: 0,
    warning: 1,
    neutral: 2,
    negative: 3,
  }[tone] ?? 4;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
