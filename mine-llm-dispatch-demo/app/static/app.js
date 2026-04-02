(function () {
  const state = {
    conversation: loadConversation(),
    selectedWorkflowId: localStorage.getItem("mine-dispatch-selected-workflow") || "",
    workflows: [],
  };

  const elements = {};

  document.addEventListener("DOMContentLoaded", () => {
    bindElements();
    bindEvents();
    renderConversation();
    updateWorkflowContext();
    void refreshDashboard();
    void refreshWorkflows();
  });

  function bindElements() {
    elements.snapshotBadge = document.getElementById("snapshot-badge");
    elements.snapshotCards = document.getElementById("snapshot-cards");
    elements.metricsCards = document.getElementById("metrics-cards");
    elements.workflowList = document.getElementById("workflow-list");
    elements.workflowEmpty = document.getElementById("workflow-empty");
    elements.workflowIdInput = document.getElementById("workflow-id");
    elements.chatContext = document.getElementById("chat-context");
    elements.chatFeed = document.getElementById("chat-feed");
    elements.chatForm = document.getElementById("chat-form");
    elements.chatInput = document.getElementById("chat-input");
    elements.sinceMinutes = document.getElementById("since-minutes");
    elements.refreshDashboard = document.getElementById("refresh-dashboard");
    elements.refreshMetrics = document.getElementById("refresh-metrics");
    elements.runWorkflow = document.getElementById("run-workflow");
    elements.clearWorkflow = document.getElementById("clear-workflow");
    elements.toast = document.getElementById("toast");
    elements.workflowIdInput.value = state.selectedWorkflowId;
  }

  function bindEvents() {
    elements.refreshDashboard.addEventListener("click", () => {
      void refreshDashboard();
      void refreshWorkflows();
    });
    elements.refreshMetrics.addEventListener("click", () => void refreshMetrics());
    elements.runWorkflow.addEventListener("click", () => void runWorkflow());
    elements.clearWorkflow.addEventListener("click", () => {
      selectWorkflow("");
      showToast("已清空 workflow 上下文");
    });
    elements.workflowIdInput.addEventListener("change", () => {
      selectWorkflow(elements.workflowIdInput.value.trim());
    });
    elements.chatForm.addEventListener("submit", (event) => {
      event.preventDefault();
      void sendChat();
    });
    document.querySelectorAll("[data-prompt]").forEach((button) => {
      button.addEventListener("click", () => {
        elements.chatInput.value = button.getAttribute("data-prompt") || "";
        elements.chatInput.focus();
      });
    });
  }

  async function refreshDashboard() {
    await Promise.all([refreshSnapshot(), refreshMetrics()]);
  }

  async function refreshSnapshot() {
    try {
      const snapshot = await api("/state/snapshot");
      elements.snapshotBadge.textContent = `${snapshot.snapshot_id} / v${snapshot.snapshot_version}`;
      renderSnapshotCards(snapshot);
    } catch (error) {
      renderErrorCard(elements.snapshotCards, String(error));
      showToast(`刷新快照失败：${error}`);
    }
  }

  async function refreshMetrics() {
    try {
      const metrics = await api("/metrics/summary");
      renderMetricsCards(metrics);
    } catch (error) {
      renderErrorCard(elements.metricsCards, String(error));
      showToast(`刷新指标失败：${error}`);
    }
  }

  async function refreshWorkflows() {
    try {
      const workflows = await api("/workflows?limit=20");
      state.workflows = workflows.slice().reverse();
      renderWorkflows();
    } catch (error) {
      renderErrorCard(elements.workflowList, String(error));
      showToast(`刷新工作流失败：${error}`);
    }
  }

  async function runWorkflow() {
    const sinceMinutes = readSinceMinutes();
    setButtonBusy(elements.runWorkflow, true, "生成中...");
    try {
      const workflow = await api("/workflows/incident-response", {
        method: "POST",
        body: JSON.stringify({
          since_minutes: sinceMinutes,
          operator_role: "dispatcher",
          include_diagnose: true,
          include_forecast: true,
        }),
      });
      selectWorkflow(workflow.workflow_id);
      await refreshDashboard();
      await refreshWorkflows();
      showToast(`已生成工作流 ${workflow.workflow_id}`);
      elements.chatInput.value = "这个工作流现在是什么状态？";
      elements.chatInput.focus();
    } catch (error) {
      showToast(`生成工作流失败：${error}`);
    } finally {
      setButtonBusy(elements.runWorkflow, false, "生成事件响应工作流");
    }
  }

  async function sendChat() {
    const query = elements.chatInput.value.trim();
    if (!query) {
      showToast("请输入问题");
      return;
    }
    const requestHistory = state.conversation.map(({ role, content }) => ({ role, content }));
    const payload = {
      query,
      history: requestHistory,
      workflow_id: state.selectedWorkflowId || null,
      since_minutes: readSinceMinutes(),
    };
    setButtonBusy(document.getElementById("send-chat"), true, "发送中...");
    try {
      const response = await api("/agents/assistant", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.conversation.push({ role: "user", content: query });
      state.conversation.push({
        role: "assistant",
        content: response.answer,
        payload: response,
      });
      persistConversation();
      renderConversation();
      elements.chatInput.value = "";
      maybeAdoptWorkflowContext(response);
      await Promise.all([refreshWorkflows(), refreshMetrics()]);
    } catch (error) {
      showToast(`发送失败：${error}`);
    } finally {
      setButtonBusy(document.getElementById("send-chat"), false, "发送问题");
    }
  }

  function renderSnapshotCards(snapshot) {
    const summary = snapshot.summary || {};
    const cards = [
      ["活跃车辆", summary.active_vehicle_count ?? 0],
      ["活跃告警", summary.active_alarm_count ?? 0],
      ["封控路段", summary.blocked_road_count ?? 0],
      ["建议路线数", Object.keys(snapshot.last_suggested_routes || {}).length],
    ];
    elements.snapshotCards.innerHTML = cards
      .map(
        ([label, value]) => `
          <article class="stat-card">
            <div class="stat-label">${escapeHtml(String(label))}</div>
            <div class="stat-value">${escapeHtml(String(value))}</div>
          </article>
        `,
      )
      .join("");
  }

  function renderMetricsCards(metrics) {
    const cards = [
      ["审批通过", metrics.workflow_approved_count ?? 0],
      ["待审批", metrics.workflow_pending_approval_count ?? 0],
      ["Gatekeeper 驳回率", toPct(metrics.gatekeeper_reject_rate)],
      ["LLM 回退率", toPct(metrics.llm_fallback_rate)],
      ["重复遥测", metrics.duplicate_telemetry_count ?? 0],
      ["重复告警", metrics.duplicate_alarm_count ?? 0],
    ];
    elements.metricsCards.innerHTML = cards
      .map(
        ([label, value]) => `
          <article class="metric-card">
            <div class="metric-label">${escapeHtml(String(label))}</div>
            <div class="metric-value">${escapeHtml(String(value))}</div>
          </article>
        `,
      )
      .join("");
  }

  function renderWorkflows() {
    elements.workflowList.innerHTML = "";
    elements.workflowEmpty.style.display = state.workflows.length ? "none" : "block";
    for (const workflow of state.workflows) {
      const card = document.createElement("article");
      card.className = `workflow-card${workflow.workflow_id === state.selectedWorkflowId ? " is-active" : ""}`;
      card.innerHTML = `
        <div class="workflow-topline">
          <strong>${escapeHtml(workflow.workflow_id)}</strong>
          <span class="status-pill ${workflow.final_status === "PASS" ? "pass" : "fail"}">
            ${escapeHtml(workflow.approval_status)}
          </span>
        </div>
        <div class="workflow-meta">incident: ${escapeHtml(workflow.incident_id)}</div>
        <div class="workflow-meta">snapshot: ${escapeHtml(workflow.snapshot_id)} / v${escapeHtml(String(workflow.snapshot_version))}</div>
        <div class="workflow-meta">revision: ${escapeHtml(String(workflow.proposal_revision))}</div>
      `;
      card.addEventListener("click", () => selectWorkflow(workflow.workflow_id));
      elements.workflowList.appendChild(card);
    }
  }

  function renderConversation() {
    elements.chatFeed.innerHTML = "";
    if (!state.conversation.length) {
      const welcome = document.createElement("article");
      welcome.className = "message assistant";
      welcome.innerHTML = `
        <div class="message-head">
          <span class="message-role">助手</span>
          <span class="message-meta">就绪</span>
        </div>
        <div class="message-body">你可以先问“当前最高优先级告警是什么？”，也可以先生成一个工作流，再围绕该 workflow 追问状态和执行条件。</div>
      `;
      elements.chatFeed.appendChild(welcome);
      return;
    }

    for (const message of state.conversation) {
      const card = document.createElement("article");
      card.className = `message ${message.role}`;
      const meta = message.role === "assistant" && message.payload ? renderAssistantMeta(message.payload) : "";
      card.innerHTML = `
        <div class="message-head">
          <span class="message-role">${message.role === "user" ? "你" : "助手"}</span>
          <span class="message-meta">${message.role === "assistant" ? "structured response" : "query"}</span>
        </div>
        <div class="message-body">${escapeHtml(message.content)}</div>
        ${meta}
      `;
      bindMessageActions(card);
      elements.chatFeed.appendChild(card);
    }
    elements.chatFeed.scrollTop = elements.chatFeed.scrollHeight;
  }

  function renderAssistantMeta(payload) {
    const lists = [];
    if (payload.suggested_actions?.length) {
      lists.push(renderListSection("建议动作", payload.suggested_actions));
    }
    if (payload.follow_up_questions?.length) {
      lists.push(renderPromptSection("继续追问", payload.follow_up_questions));
    }
    if (payload.related_workflows?.length) {
      lists.push(
        `<div class="message-tags">${payload.related_workflows
          .map(
            (item) =>
              `<button type="button" class="message-tag js-workflow-tag" data-workflow-id="${escapeAttr(
                item.workflow_id,
              )}">${escapeHtml(item.workflow_id)} · ${escapeHtml(item.approval_status)}</button>`,
          )
          .join("")}</div>`,
      );
    }
    if (payload.evidence?.length) {
      lists.push(
        `<div class="message-tags">${payload.evidence
          .slice(0, 6)
          .map((item) => `<span class="message-tag">${escapeHtml(item)}</span>`)
          .join("")}</div>`,
      );
    }
    return lists.join("");
  }

  function renderListSection(title, items) {
    return `
      <div class="message-meta">${escapeHtml(title)}</div>
      <ul class="message-list">
        ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    `;
  }

  function renderPromptSection(title, items) {
    return `
      <div class="message-meta">${escapeHtml(title)}</div>
      <div class="message-tags">
        ${items
          .map(
            (item) =>
              `<button type="button" class="message-tag js-follow-up" data-prompt="${escapeAttr(item)}">${escapeHtml(
                item,
              )}</button>`,
          )
          .join("")}
      </div>
    `;
  }

  function bindMessageActions(card) {
    card.querySelectorAll(".js-follow-up").forEach((button) => {
      button.addEventListener("click", () => {
        elements.chatInput.value = button.getAttribute("data-prompt") || "";
        elements.chatInput.focus();
      });
    });
    card.querySelectorAll(".js-workflow-tag").forEach((button) => {
      button.addEventListener("click", () => {
        selectWorkflow(button.getAttribute("data-workflow-id") || "");
        showToast(`已切换到 ${button.getAttribute("data-workflow-id")}`);
      });
    });
  }

  function maybeAdoptWorkflowContext(payload) {
    const firstWorkflow = payload.related_workflows?.[0]?.workflow_id;
    if (firstWorkflow && !state.selectedWorkflowId) {
      selectWorkflow(firstWorkflow);
    }
  }

  function selectWorkflow(workflowId) {
    state.selectedWorkflowId = workflowId;
    elements.workflowIdInput.value = workflowId;
    updateWorkflowContext();
    persistWorkflowSelection();
    renderWorkflows();
  }

  function updateWorkflowContext() {
    if (state.selectedWorkflowId) {
      elements.chatContext.textContent = `上下文 ${state.selectedWorkflowId}`;
      elements.chatContext.classList.add("badge-accent");
    } else {
      elements.chatContext.textContent = "无工作流上下文";
      elements.chatContext.classList.add("badge-accent");
    }
  }

  function loadConversation() {
    const raw = localStorage.getItem("mine-dispatch-conversation");
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(-12) : [];
    } catch {
      return [];
    }
  }

  function persistConversation() {
    localStorage.setItem("mine-dispatch-conversation", JSON.stringify(state.conversation.slice(-12)));
  }

  function persistWorkflowSelection() {
    localStorage.setItem("mine-dispatch-selected-workflow", state.selectedWorkflowId);
  }

  function readSinceMinutes() {
    const raw = Number(elements.sinceMinutes.value);
    return Number.isFinite(raw) && raw > 0 ? raw : 10;
  }

  function setButtonBusy(button, busy, label) {
    if (!button) {
      return;
    }
    button.disabled = busy;
    button.textContent = label;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
      },
      ...options,
    });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch {
        detail = await response.text();
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function renderErrorCard(container, message) {
    container.innerHTML = `<div class="empty-state">加载失败：${escapeHtml(message)}</div>`;
  }

  function toPct(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "0%";
    }
    return `${(value * 100).toFixed(1)}%`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add("is-visible");
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(() => {
      elements.toast.classList.remove("is-visible");
    }, 2600);
  }
})();
