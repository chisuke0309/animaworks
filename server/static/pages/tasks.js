import { api } from "../modules/api.js";

let _container = null;
let _tasks = [];
let _selectedRootId = null;

export async function render(container) {
    _container = container;

    container.innerHTML = `
    <div class="tasks-page-layout">
      <div class="tasks-sidebar">
        <div class="tasks-sidebar-header">
          <h2>タスク管理</h2>
          <button id="tasksRefreshBtn" class="tasks-refresh-btn" title="更新">🔄</button>
        </div>
        <div class="tasks-list" id="tasksList">
          <div class="tasks-loading">読み込み中...</div>
        </div>
      </div>

      <div class="tasks-main">
        <div class="tasks-main-empty" id="tasksEmptyState">
          タスクを選択して詳細を表示
        </div>
        <div class="tasks-detail-view" id="tasksDetailView" style="display:none;">
          <div class="tasks-detail-header">
            <div class="tasks-detail-title-row">
              <h3 id="taskTitle"></h3>
              <div class="task-meta" id="taskMeta"></div>
            </div>
            <div class="tasks-detail-route" id="taskRoute"></div>
          </div>
          <div class="tasks-chat-timeline" id="tasksChatTimeline"></div>
        </div>
      </div>
    </div>
  `;

    document.getElementById("tasksRefreshBtn").addEventListener("click", loadTasks);
    await loadTasks();
}

async function loadTasks() {
    const listEl = document.getElementById("tasksList");
    listEl.innerHTML = '<div class="tasks-loading">読み込み中...</div>';
    try {
        _tasks = await api("/api/tasks");
        renderTaskList();
    } catch (err) {
        console.error("Failed to load tasks:", err);
        listEl.innerHTML = '<div class="tasks-error">タスクの読み込みに失敗しました</div>';
    }
}

function statusLabel(status) {
    const map = {
        pending: "⏳ pending",
        in_progress: "🔄 in_progress",
        done: "✅ done",
        completed: "✅ completed",
        blocked: "🚫 blocked",
        cancelled: "❌ cancelled",
        delegated: "↗️ delegated",
    };
    return map[status] || status;
}

function renderTaskList() {
    const listEl = document.getElementById("tasksList");
    listEl.innerHTML = "";

    if (_tasks.length === 0) {
        listEl.innerHTML = '<div class="tasks-empty">タスクはありません</div>';
        return;
    }

    _tasks.forEach(task => {
        const item = document.createElement("div");
        item.className = "task-item";
        if (task.root_task_id === _selectedRootId) item.classList.add("active");

        const relay = task.relay_chain || [];
        const delegator = relay[0] || (task.source === "anima" ? "anima" : "—");
        const subCount = (task.sub_tasks || []).length;
        const subBadge = subCount > 0
            ? `<span class="task-sub-count">${subCount} steps</span>`
            : "";

        item.innerHTML = `
      <div class="task-item-title">${escapeHtml(task.summary || "無題のタスク")}</div>
      <div class="task-item-meta">
        <span class="task-status status-${task.status}">${statusLabel(task.status)}</span>
        <span class="task-route">${escapeHtml(delegator)} → ${escapeHtml(task.assignee)}</span>
        ${subBadge}
      </div>
    `;
        item.addEventListener("click", () => selectTask(task));
        listEl.appendChild(item);
    });
}

async function selectTask(task) {
    _selectedRootId = task.root_task_id || task.task_id;
    renderTaskList();

    document.getElementById("tasksEmptyState").style.display = "none";
    const detailView = document.getElementById("tasksDetailView");
    detailView.style.display = "flex";

    const relay = task.relay_chain || [];
    const delegator = relay[0] || (task.source === "anima" ? "anima" : "—");

    document.getElementById("taskTitle").textContent = task.summary || "無題のタスク";
    document.getElementById("taskMeta").innerHTML =
        `<span class="task-status status-${task.status}">${statusLabel(task.status)}</span>`;
    document.getElementById("taskRoute").textContent =
        `${delegator} → ${task.assignee}　　${formatTs(task.ts)}`;

    const timeline = document.getElementById("tasksChatTimeline");
    timeline.innerHTML = '<div class="tasks-loading">読み込み中...</div>';

    try {
        const events = await api(`/api/tasks/${task.task_id}/messages`);
        renderTimeline(events);
    } catch (err) {
        console.error("Failed to load task messages:", err);
        timeline.innerHTML = '<div class="tasks-error">読み込みエラー</div>';
    }
}

function renderTimeline(events) {
    const timeline = document.getElementById("tasksChatTimeline");
    timeline.innerHTML = "";

    if (events.length === 0) {
        timeline.innerHTML = '<div class="tasks-empty">メッセージなし</div>';
        return;
    }

    events.forEach(ev => {
        if (ev.event_kind === "instruction") {
            timeline.appendChild(buildInstruction(ev));
        } else if (ev.event_kind === "status_update") {
            timeline.appendChild(buildStatusEvent(ev));
        } else {
            timeline.appendChild(buildMessage(ev));
        }
    });
}

function buildInstruction(ev) {
    const el = document.createElement("div");
    el.className = "tl-instruction";
    el.innerHTML = `
    <div class="tl-instruction-header">
      <span class="tl-sender">${escapeHtml(ev.from_person || "")}</span>
      <span class="tl-arrow">→</span>
      <span class="tl-assignee">${escapeHtml(ev.to_person || "")}</span>
      <span class="tl-time">${formatTs(ev.ts)}</span>
      <span class="tl-badge">指示</span>
    </div>
    <div class="tl-instruction-body">${escapeHtml(ev.content || "")}</div>
  `;
    return el;
}

function buildStatusEvent(ev) {
    const el = document.createElement("div");
    el.className = "tl-status-event";
    const status = ev.status || ev.meta?.status || "";
    el.innerHTML = `
    <span class="tl-status-dot status-${status}"></span>
    <span>${escapeHtml(ev.summary || status)}</span>
    <span class="tl-time">${formatTs(ev.ts)}</span>
  `;
    return el;
}

function buildMessage(ev) {
    const sender = ev.from_person || "";
    // Messages sent by the assignee appear on the right
    const isRight = ev.type === "message_sent";
    const el = document.createElement("div");
    el.className = `tl-message ${isRight ? "tl-message-right" : "tl-message-left"}`;
    el.innerHTML = `
    <div class="tl-bubble">
      <div class="tl-bubble-header">
        <span class="tl-sender">${escapeHtml(sender || "—")}</span>
        <span class="tl-time">${formatTs(ev.ts)}</span>
      </div>
      <div class="tl-bubble-body">${escapeHtml(ev.content || "")}</div>
    </div>
  `;
    return el;
}

function formatTs(ts) {
    if (!ts) return "";
    try {
        return new Date(ts).toLocaleString("ja-JP", {
            month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

function escapeHtml(unsafe) {
    return (unsafe || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function destroy() {
    _container = null;
    _tasks = [];
    _selectedRootId = null;
}
