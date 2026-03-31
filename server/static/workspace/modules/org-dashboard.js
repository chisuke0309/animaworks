/**
 * Organization dashboard view for the Workspace.
 * 2-column layout:
 * - Main (flex): Interactive organization tree with inline status
 * - Right (300px): Real-time activity feed
 */
import { createLogger } from "../../shared/logger.js";
import { escapeHtml, smartTimestamp } from "./utils.js";
import { animaHashColor } from "../../shared/avatar-utils.js";

const logger = createLogger("org-dashboard");

let _container = null;
let _treeNodes = new Map();
let _activityFeed = null;
let _onNodeClick = null;
const MAX_ACTIVITY_ITEMS = 50;

// ── Org Tree Builder ──────────────────────

function buildOrgTree(animas) {
  const nodeMap = new Map();
  for (const p of animas) {
    nodeMap.set(p.name, {
      name: p.name,
      role: p.role || null,
      speciality: p.speciality || null,
      supervisor: p.supervisor || null,
      status: p.status,
      children: [],
    });
  }
  const roots = [];
  for (const node of nodeMap.values()) {
    if (node.role === "commander" || !node.supervisor || !nodeMap.has(node.supervisor)) {
      roots.push(node);
    } else {
      const parent = nodeMap.get(node.supervisor);
      if (parent) parent.children.push(node);
    }
  }
  return roots.length ? roots : [...nodeMap.values()];
}

function getStatusDotClass(status) {
  if (!status) return "dot-unknown";
  const s = typeof status === "object" ? (status.state || status.status || "") : String(status);
  const lower = s.toLowerCase();
  if (lower === "idle") return "dot-idle";
  if (lower === "thinking" || lower === "working") return "dot-active";
  if (lower === "sleeping" || lower === "stopped" || lower === "not_found") return "dot-sleeping";
  if (lower.includes("error")) return "dot-error";
  if (lower.includes("bootstrap")) return "dot-bootstrap";
  return "dot-unknown";
}

function getStatusLabel(status) {
  if (!status) return "unknown";
  const s = typeof status === "object" ? (status.state || status.status || "unknown") : String(status);
  return s.toLowerCase();
}

// ── Interactive Tree Node ──────────────────────

function renderInteractiveTreeNode(node, depth = 0, isLast = true, prefixLines = []) {
  const statusDot = getStatusDotClass(node.status);
  const statusLabel = getStatusLabel(node.status);
  const initial = (node.name || "?")[0].toUpperCase();
  const color = animaHashColor(node.name);

  let connector = "";
  if (depth > 0) {
    const prefix = prefixLines.map(hasLine => hasLine ? '<span class="org-itree-vline"></span>' : '<span class="org-itree-spacer"></span>').join("");
    const branch = isLast ? '<span class="org-itree-elbow"></span>' : '<span class="org-itree-tee"></span>';
    connector = `<span class="org-itree-connector">${prefix}${branch}</span>`;
  }

  const roleLabel = node.role || "";
  const specLabel = node.speciality || "";
  const tagHtml = roleLabel || specLabel
    ? `<span class="org-itree-tags">${roleLabel ? `<span class="org-itree-role">${escapeHtml(roleLabel)}</span>` : ""}${specLabel ? `<span class="org-itree-spec">${escapeHtml(specLabel)}</span>` : ""}</span>`
    : "";

  let html = `<div class="org-itree-node" data-name="${escapeHtml(node.name)}" id="orgNode_${escapeHtml(node.name)}">
    ${connector}
    <div class="org-itree-card">
      <div class="org-itree-avatar" style="background:${color}">${initial}</div>
      <div class="org-itree-info">
        <span class="org-itree-name">${escapeHtml(node.name)}</span>
        ${tagHtml}
      </div>
      <span class="org-itree-status">
        <span class="org-itree-dot ${statusDot}"></span>
        <span class="org-itree-status-label">${escapeHtml(statusLabel)}</span>
      </span>
    </div>
  </div>`;

  const childPrefixLines = [...prefixLines, !isLast];
  for (let i = 0; i < node.children.length; i++) {
    const childIsLast = i === node.children.length - 1;
    html += renderInteractiveTreeNode(node.children[i], depth + 1, childIsLast, childPrefixLines);
  }
  return html;
}

// ── Activity Feed ──────────────────────

function renderActivityItem(item) {
  const time = smartTimestamp(item.ts || item.timestamp || "");
  const icon = item.type === "error" ? "⚠️" : "📌";
  const from = item.from ? `<span class="org-activity-from">${escapeHtml(item.from)}</span>` : "";
  const summary = escapeHtml(item.summary || item.content || item.type || "");
  return `<div class="org-activity-item">
    <span class="org-activity-icon">${icon}</span>
    <div class="org-activity-body">
      ${from}
      <span class="org-activity-text">${summary}</span>
    </div>
    <span class="org-activity-time">${time}</span>
  </div>`;
}

function addActivityItem(item) {
  if (!_activityFeed) return;
  const div = document.createElement("div");
  div.innerHTML = renderActivityItem(item);
  const el = div.firstElementChild;
  _activityFeed.prepend(el);
  while (_activityFeed.children.length > MAX_ACTIVITY_ITEMS) {
    _activityFeed.removeChild(_activityFeed.lastElementChild);
  }
}

// ── Main API ──────────────────────

export async function initOrgDashboard(container, animas, { onNodeClick } = {}) {
  _container = container;
  _treeNodes.clear();
  _onNodeClick = onNodeClick || null;

  const roots = buildOrgTree(animas);

  let treeHtml = "";
  for (let i = 0; i < roots.length; i++) {
    treeHtml += renderInteractiveTreeNode(roots[i], 0, i === roots.length - 1, []);
  }

  container.innerHTML = `
    <div class="org-dashboard">
      <div class="org-col-main">
        <div class="org-section-title">
          <button class="org-goals-btn" id="orgGoalsBtn" title="組織目標を表示">組織 <span class="org-goals-icon">🎯</span></button>
        </div>
        <div class="org-itree">${treeHtml}</div>
      </div>
      <div class="org-col-right">
        <div class="org-section-title">アクティビティ</div>
        <div class="org-activity-feed" id="orgActivityFeed"></div>
      </div>
    </div>
    <!-- Goals Panel -->
    <div class="org-goals-panel hidden" id="orgGoalsPanel">
      <div class="org-goals-panel-header">
        <span>🎯 組織目標</span>
        <div class="org-goals-panel-actions">
          <button class="org-goals-edit-btn" id="orgGoalsEditBtn">編集</button>
          <button class="org-goals-save-btn hidden" id="orgGoalsSaveBtn">保存</button>
          <button class="org-goals-cancel-btn hidden" id="orgGoalsCancelBtn">✕</button>
          <button class="org-goals-close-btn" id="orgGoalsCloseBtn">✕ 閉じる</button>
        </div>
      </div>
      <div class="org-goals-tabs" id="orgGoalsTabs">
        <button class="org-goals-tab active" data-unit="all">すべて</button>
        <button class="org-goals-tab" data-unit="x">X事業部</button>
        <button class="org-goals-tab" data-unit="tiktok">TikTok事業部</button>
      </div>
      <div class="org-goals-panel-body">
        <div id="orgGoalsContent" class="org-goals-content"></div>
        <textarea id="orgGoalsEditor" class="org-goals-editor hidden"></textarea>
      </div>
    </div>
  `;

  _activityFeed = document.getElementById("orgActivityFeed");

  for (const p of animas) {
    _treeNodes.set(p.name, document.getElementById(`orgNode_${p.name}`));
  }

  // Load recent activity
  try {
    const resp = await fetch("/api/activity/recent?hours=12&limit=20");
    if (resp.ok) {
      const data = await resp.json();
      const items = Array.isArray(data) ? data : (data.events || []);
      for (const item of items.reverse()) {
        addActivityItem(item);
      }
    }
  } catch (err) {
    logger.warn("Failed to load activity", { error: err.message });
  }

  // Tree node click → select anima
  container.addEventListener("click", (e) => {
    const node = e.target.closest(".org-itree-node");
    if (!node) return;
    const name = node.dataset.name;
    if (!name) return;

    container.querySelectorAll(".org-itree-node.selected").forEach(el => el.classList.remove("selected"));
    node.classList.add("selected");

    if (_onNodeClick) _onNodeClick(name);
  });

  // Goals panel
  document.getElementById("orgGoalsBtn").addEventListener("click", openGoalsPanel);
  document.getElementById("orgGoalsCloseBtn").addEventListener("click", closeGoalsPanel);
  document.getElementById("orgGoalsEditBtn").addEventListener("click", startGoalsEdit);
  document.getElementById("orgGoalsSaveBtn").addEventListener("click", saveGoals);
  document.getElementById("orgGoalsCancelBtn").addEventListener("click", cancelGoalsEdit);

  // Goals tabs
  document.getElementById("orgGoalsTabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".org-goals-tab");
    if (!btn) return;
    _activeGoalsUnit = btn.dataset.unit;
    document.querySelectorAll("#orgGoalsTabs .org-goals-tab").forEach(b => b.classList.toggle("active", b === btn));
    renderGoalsView();
  });

  logger.info("Org dashboard initialized", { animaCount: animas.length });
}

// ── Goals Panel ───────────────────────────

let _goalsContent = "";
let _activeGoalsUnit = "all";

async function openGoalsPanel() {
  const panel = document.getElementById("orgGoalsPanel");
  const content = document.getElementById("orgGoalsContent");
  panel.classList.remove("hidden");
  content.innerHTML = `<div style="padding:1rem;color:#888">読み込み中...</div>`;
  try {
    const resp = await fetch("/api/common-knowledge/organization/goals.md");
    const data = await resp.json();
    _goalsContent = data.content || "";
    renderGoalsView();
  } catch (e) {
    content.innerHTML = `<div style="padding:1rem;color:red">読み込み失敗: ${e.message}</div>`;
  }
}

function closeGoalsPanel() {
  const panel = document.getElementById("orgGoalsPanel");
  panel.classList.add("hidden");
  cancelGoalsEdit();
}

function _filterGoalsByUnit(md, unit) {
  if (unit === "all") return md;
  // Split by <!-- unit:xxx --> markers and keep matching section
  const sections = md.split(/(?=<!-- unit:\w+ -->)/);
  const filtered = sections.filter(s => {
    const match = s.match(/<!-- unit:(\w+) -->/);
    if (!match) return true; // keep header/preamble
    return match[1] === unit;
  });
  return filtered.join("");
}

function renderGoalsView() {
  const filtered = _filterGoalsByUnit(_goalsContent, _activeGoalsUnit);
  document.getElementById("orgGoalsContent").innerHTML = simpleMarkdown(filtered);
  document.getElementById("orgGoalsContent").classList.remove("hidden");
  document.getElementById("orgGoalsEditor").classList.add("hidden");
  document.getElementById("orgGoalsEditBtn").classList.remove("hidden");
  document.getElementById("orgGoalsSaveBtn").classList.add("hidden");
  document.getElementById("orgGoalsCancelBtn").classList.add("hidden");
}

function startGoalsEdit() {
  document.getElementById("orgGoalsEditor").value = _goalsContent;
  document.getElementById("orgGoalsContent").classList.add("hidden");
  document.getElementById("orgGoalsEditor").classList.remove("hidden");
  document.getElementById("orgGoalsEditBtn").classList.add("hidden");
  document.getElementById("orgGoalsSaveBtn").classList.remove("hidden");
  document.getElementById("orgGoalsCancelBtn").classList.remove("hidden");
}

async function saveGoals() {
  const btn = document.getElementById("orgGoalsSaveBtn");
  _goalsContent = document.getElementById("orgGoalsEditor").value;
  btn.textContent = "保存中...";
  btn.disabled = true;
  try {
    await fetch("/api/common-knowledge/organization/goals.md", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: _goalsContent }),
    });
    renderGoalsView();
  } catch (e) {
    alert(`保存失敗: ${e.message}`);
  } finally {
    btn.textContent = "保存";
    btn.disabled = false;
  }
}

function cancelGoalsEdit() {
  renderGoalsView();
}

function simpleMarkdown(md) {
  return md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^---$/gm, "<hr>")
    .replace(/^\| ?(.+?) ?\|$/gm, (line) => {
      if (/^[\s|:-]+$/.test(line)) return "";
      const cells = line.split("|").filter((_, i, a) => i > 0 && i < a.length - 1);
      return "<tr>" + cells.map(c => `<td>${c.trim()}</td>`).join("") + "</tr>";
    })
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*?<\/li>\s*)+/gs, m => `<ul>${m}</ul>`)
    .replace(/(<tr>.*?<\/tr>\s*)+/gs, m => `<table class="org-goals-table">${m}</table>`)
    .replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>")
    .replace(/^/, "<p>").replace(/$/, "</p>");
}

export function disposeOrgDashboard() {
  if (_container) {
    _container.innerHTML = "";
  }
  _treeNodes.clear();
  _activityFeed = null;
  _container = null;
  _onNodeClick = null;
}

export function updateAnimaStatus(name, status) {
  const nodeEl = _treeNodes.get(name);
  if (!nodeEl) return;

  const state = typeof status === "object" ? (status.state || status.status || "unknown") : String(status);
  const dotClass = getStatusDotClass(status);

  const dot = nodeEl.querySelector(".org-itree-dot");
  if (dot) dot.className = `org-itree-dot ${dotClass}`;

  const label = nodeEl.querySelector(".org-itree-status-label");
  if (label) label.textContent = state.toLowerCase();
}

export { addActivityItem };
