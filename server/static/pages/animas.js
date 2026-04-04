// ── Anima Management ───────────────────────
import { api } from "../modules/api.js";
import { escapeHtml, statusClass, renderMarkdown } from "../modules/state.js";
import { t } from "/shared/i18n.js";

let _viewMode = "list"; // "list" | "detail"
let _selectedName = null;
let _container = null;

function _extractStatsCount(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (value && typeof value === "object") {
    const count = value.count;
    if (typeof count === "number" && Number.isFinite(count)) return count;
  }
  return 0;
}

export function render(container) {
  _container = container;
  _viewMode = "list";
  _selectedName = null;
  _renderList();
}

export function destroy() {
  _container = null;
  _viewMode = "list";
  _selectedName = null;
}

// ── List View ──────────────────────────────

async function _renderList() {
  if (!_container) return;

  _container.innerHTML = `
    <div class="page-header">
      <h2>${t("nav.animas")}</h2>
    </div>
    <div id="animasListContent">
      <div class="loading-placeholder">${t("common.loading")}</div>
    </div>
  `;

  const content = document.getElementById("animasListContent");
  if (!content) return;

  try {
    const animas = await api("/api/animas");

    if (animas.length === 0) {
      content.innerHTML = `<div class="loading-placeholder">${t("animas.not_registered")}</div>`;
      return;
    }

    content.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>名前</th>
            <th>ステータス</th>
            <th>PID</th>
            <th>稼働時間</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="animasTableBody"></tbody>
      </table>
    `;

    const tbody = document.getElementById("animasTableBody");
    for (const p of animas) {
      const dotClass = statusClass(p.status);
      const statusLabel = p.status || "offline";
      const uptime = p.uptime_sec ? _formatUptime(p.uptime_sec) : "--";
      const pid = p.pid || "--";

      // Determine visual state class
      let stateClass = "";
      if (p.status === "bootstrapping" || p.bootstrapping) {
        stateClass = "anima-item anima-item--loading";
      } else if (p.status === "not_found" || p.status === "stopped") {
        stateClass = "anima-item anima-item--sleeping";
      } else {
        stateClass = "anima-item";
      }

      const tr = document.createElement("tr");
      tr.className = stateClass;
      tr.dataset.anima = p.name;
      tr.style.cursor = "pointer";
      tr.innerHTML = `
        <td style="font-weight:600;">${escapeHtml(p.name)}</td>
        <td>
          <span class="status-dot ${dotClass}" style="display:inline-block;"></span>
          ${escapeHtml(statusLabel)}
        </td>
        <td>${escapeHtml(String(pid))}</td>
        <td>${escapeHtml(uptime)}</td>
        <td>
          <button class="btn-secondary anima-detail-btn" data-name="${escapeHtml(p.name)}" style="font-size:0.8rem; padding:0.25rem 0.5rem;">詳細</button>
          <button class="btn-primary anima-trigger-btn" data-name="${escapeHtml(p.name)}" style="font-size:0.8rem; padding:0.25rem 0.5rem;">Heartbeat</button>
        </td>
      `;

      tr.addEventListener("click", (e) => {
        if (e.target.classList.contains("anima-trigger-btn")) return;
        _showDetail(p.name);
      });

      tbody.appendChild(tr);
    }

    // Bind trigger buttons
    content.querySelectorAll(".anima-trigger-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const name = btn.dataset.name;
        btn.disabled = true;
        btn.textContent = "実行中...";
        try {
          await fetch(`/api/animas/${encodeURIComponent(name)}/trigger`, { method: "POST" });
          btn.textContent = "完了";
          setTimeout(() => { btn.textContent = "Heartbeat"; btn.disabled = false; }, 2000);
        } catch {
          btn.textContent = "失敗";
          setTimeout(() => { btn.textContent = "Heartbeat"; btn.disabled = false; }, 2000);
        }
      });
    });

  } catch (err) {
    content.innerHTML = `<div class="loading-placeholder">${t("common.load_failed")}: ${escapeHtml(err.message)}</div>`;
  }
}

// ── Detail View ────────────────────────────

async function _showDetail(name) {
  if (!_container) return;
  _viewMode = "detail";
  _selectedName = name;

  _container.innerHTML = `
    <div class="page-header" style="display:flex; align-items:center; gap:1rem;">
      <button class="btn-secondary" id="animasBackBtn" style="font-size:0.85rem;">&larr; ${t("animas.back")}</button>
      <h2>${escapeHtml(name)}</h2>
    </div>
    <div id="animasDetailContent">
      <div class="loading-placeholder">${t("common.loading")}</div>
    </div>
  `;

  document.getElementById("animasBackBtn").addEventListener("click", () => {
    _viewMode = "list";
    _selectedName = null;
    _renderList();
  });

  const content = document.getElementById("animasDetailContent");
  if (!content) return;

  try {
    const detail = await api(`/api/animas/${encodeURIComponent(name)}`);

    // Try optional endpoints
    let animaConfig = null;
    let memoryStats = null;
    try { animaConfig = await api(`/api/animas/${encodeURIComponent(name)}/config`); } catch { /* 404 ok */ }
    try { memoryStats = await api(`/api/animas/${encodeURIComponent(name)}/memory/stats`); } catch { /* 404 ok */ }

    let html = '<div class="card-grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 1.5rem;">';

    // Identity card
    html += `
      <div class="card">
        <div class="card-header">${t("animas.identity")}</div>
        <div class="card-body" style="max-height:300px; overflow-y:auto;">
          ${detail.identity ? renderMarkdown(detail.identity) : `<span style="color:var(--text-secondary, #666);">${t("animas.not_set")}</span>`}
        </div>
      </div>
    `;

    // Injection card
    html += `
      <div class="card">
        <div class="card-header">${t("animas.injection")}</div>
        <div class="card-body" style="max-height:300px; overflow-y:auto;">
          ${detail.injection ? renderMarkdown(detail.injection) : `<span style="color:var(--text-secondary, #666);">${t("animas.not_set")}</span>`}
        </div>
      </div>
    `;

    html += "</div>";

    // State + Pending
    html += '<div class="card-grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 1.5rem;">';

    html += `
      <div class="card">
        <div class="card-header">${t("animas.state_current")}</div>
        <div class="card-body">
          <pre style="white-space:pre-wrap; word-break:break-word; margin:0;">${escapeHtml(
            detail.state ? (typeof detail.state === "string" ? detail.state : JSON.stringify(detail.state, null, 2)) : t("animas.no_state")
          )}</pre>
        </div>
      </div>
    `;

    html += `
      <div class="card">
        <div class="card-header">${t("animas.pending")}</div>
        <div class="card-body">
          <pre style="white-space:pre-wrap; word-break:break-word; margin:0;">${escapeHtml(
            detail.pending ? (typeof detail.pending === "string" ? detail.pending : JSON.stringify(detail.pending, null, 2)) : t("animas.no_pending")
          )}</pre>
        </div>
      </div>
    `;

    html += "</div>";

    // Memory stats
    const epCount = detail.episode_files?.length ?? _extractStatsCount(memoryStats?.episodes);
    const knCount = detail.knowledge_files?.length ?? _extractStatsCount(memoryStats?.knowledge);
    const prCount = detail.procedure_files?.length ?? _extractStatsCount(memoryStats?.procedures);

    html += `
      <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 1.5rem;">
        <div class="stat-card">
          <div class="stat-label">${t("chat.memory_episodes")}</div>
          <div class="stat-value">${epCount}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">${t("chat.memory_knowledge")}</div>
          <div class="stat-value">${knCount}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">${t("chat.memory_procedures")}</div>
          <div class="stat-value">${prCount}</div>
        </div>
      </div>
    `;

    // Model config — editable dropdown
    {
      const MODELS = [
        { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
        { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
        { value: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
        { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 (Oct)" },
      ];
      const currentModel = animaConfig?.model || detail?.status?.model || "";
      const options = MODELS.map((m) => {
        const sel = (m.value === currentModel || currentModel.startsWith(m.value)) ? "selected" : "";
        return `<option value="${m.value}" ${sel}>${m.label}</option>`;
      }).join("");
      const isKnown = MODELS.some((m) => currentModel === m.value || currentModel.startsWith(m.value));
      const extra = !isKnown && currentModel
        ? `<option value="${escapeHtml(currentModel)}" selected>${escapeHtml(currentModel)}</option>`
        : "";

      // Heartbeat config
      const hbMode = detail.heartbeat_mode || "scheduled";
      const hbHours = detail.heartbeat_active_hours || "24h";
      let hbStart = 6, hbEnd = 22;
      if (hbHours && hbHours !== "24h") {
        const hm = hbHours.match(/(\d+):\d+\s*-\s*(\d+)/);
        if (hm) { hbStart = parseInt(hm[1]); hbEnd = parseInt(hm[2]); }
      }
      const hourOpts = (selVal) => Array.from({length: 24}, (_, i) =>
        `<option value="${i}" ${i === selVal ? "selected" : ""}>${i}:00</option>`
      ).join("");
      const isInboxOnly = hbMode === "inbox_only";

      html += `
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">${t("animas.model_config")}</div>
          <div class="card-body" style="display:flex; flex-direction:column; gap:0.75rem;">
            <div style="display:flex; align-items:center; gap:1rem;">
              <label style="font-weight:600; white-space:nowrap; min-width:100px;">Model:</label>
              <select id="animaModelSelect" style="flex:1; padding:0.4rem 0.6rem; border:1px solid var(--border, #ddd); border-radius:6px; font-size:0.9rem;">
                ${extra}${options}
              </select>
              <span id="animaModelStatus" style="font-size:0.8rem; color:var(--text-secondary, #666);"></span>
            </div>
            <div style="display:flex; align-items:center; gap:1rem;">
              <label style="font-weight:600; white-space:nowrap; min-width:100px;">Heartbeat:</label>
              <select id="animaHbMode" style="padding:0.4rem 0.6rem; border:1px solid var(--border, #ddd); border-radius:6px; font-size:0.9rem;">
                <option value="inbox_only" ${isInboxOnly ? "selected" : ""}>inbox_only</option>
                <option value="scheduled" ${!isInboxOnly ? "selected" : ""}>scheduled</option>
              </select>
              <label style="font-weight:600; white-space:nowrap;">稼働時間:</label>
              <select id="animaHbStart" style="padding:0.4rem 0.6rem; border:1px solid var(--border, #ddd); border-radius:6px; font-size:0.9rem;" ${isInboxOnly ? "disabled" : ""}>
                ${hourOpts(hbStart)}
              </select>
              <span>-</span>
              <select id="animaHbEnd" style="padding:0.4rem 0.6rem; border:1px solid var(--border, #ddd); border-radius:6px; font-size:0.9rem;" ${isInboxOnly ? "disabled" : ""}>
                ${hourOpts(hbEnd)}
              </select>
              <span id="animaHbStatus" style="font-size:0.8rem; color:var(--text-secondary, #666);"></span>
            </div>
          </div>
        </div>
      `;
    }

    // Profile / Identity editor card
    html += `
      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-header" style="display:flex; justify-content:space-between; align-items:center;">
          <span>プロフィール (identity.md)</span>
          <div style="display:flex; gap:0.5rem;">
            <button id="profileEditBtn" class="btn-secondary" style="padding:0.25rem 0.75rem; font-size:0.8rem;">編集</button>
            <button id="profileSaveBtn" class="btn-primary" style="padding:0.25rem 0.75rem; font-size:0.8rem; display:none;">保存</button>
            <button id="profileCancelBtn" class="btn-secondary" style="padding:0.25rem 0.75rem; font-size:0.8rem; display:none;">キャンセル</button>
            <span id="profileStatus" style="font-size:0.8rem; line-height:2;"></span>
          </div>
        </div>
        <div class="card-body">
          <div id="profileView" style="max-height:400px; overflow-y:auto; white-space:pre-wrap; font-size:0.85rem; line-height:1.6; font-family:inherit;">${escapeHtml(detail.identity || "(なし)")}</div>
          <textarea id="profileEditor" style="display:none; width:100%; min-height:400px; padding:0.75rem; border:1px solid var(--border, #ddd); border-radius:6px; font-size:0.85rem; line-height:1.6; font-family:monospace; resize:vertical;"></textarea>
        </div>
      </div>
    `;

    // Action buttons
    html += `
      <div style="display:flex; gap:0.75rem;">
        <button class="btn-primary" id="animaDetailTrigger">${t("animas.heartbeat_trigger")}</button>
      </div>
    `;

    content.innerHTML = html;

    // Bind model selector
    document.getElementById("animaModelSelect")?.addEventListener("change", async (e) => {
      const select = e.target;
      const statusEl = document.getElementById("animaModelStatus");
      const newModel = select.value;
      select.disabled = true;
      if (statusEl) statusEl.textContent = "Updating...";
      try {
        await fetch(`/api/animas/${encodeURIComponent(name)}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: newModel }),
        });
        if (statusEl) { statusEl.textContent = "✅ Updated"; statusEl.style.color = "#2a2"; }
        setTimeout(() => { if (statusEl) statusEl.textContent = ""; select.disabled = false; }, 2000);
      } catch (err) {
        if (statusEl) { statusEl.textContent = "❌ Failed"; statusEl.style.color = "#c22"; }
        setTimeout(() => { if (statusEl) statusEl.textContent = ""; select.disabled = false; }, 3000);
      }
    });

    // Bind heartbeat mode/hours selectors
    const hbModeEl = document.getElementById("animaHbMode");
    const hbStartEl = document.getElementById("animaHbStart");
    const hbEndEl = document.getElementById("animaHbEnd");
    const hbStatusEl = document.getElementById("animaHbStatus");

    // Toggle hours selectors when mode changes
    hbModeEl?.addEventListener("change", () => {
      const disabled = hbModeEl.value === "inbox_only";
      if (hbStartEl) hbStartEl.disabled = disabled;
      if (hbEndEl) hbEndEl.disabled = disabled;
    });

    // Save heartbeat config on any change
    const saveHbConfig = async () => {
      if (hbStatusEl) { hbStatusEl.textContent = "Updating..."; hbStatusEl.style.color = ""; }
      const mode = hbModeEl?.value || "scheduled";
      const payload = { heartbeat_mode: mode };
      if (mode === "scheduled") {
        payload.heartbeat_hours_start = parseInt(hbStartEl?.value || "6");
        payload.heartbeat_hours_end = parseInt(hbEndEl?.value || "22");
      }
      try {
        await fetch(`/api/animas/${encodeURIComponent(name)}/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (hbStatusEl) { hbStatusEl.textContent = "✅ Updated (restart required)"; hbStatusEl.style.color = "#2a2"; }
        setTimeout(() => { if (hbStatusEl) hbStatusEl.textContent = ""; }, 4000);
      } catch (err) {
        if (hbStatusEl) { hbStatusEl.textContent = "❌ Failed"; hbStatusEl.style.color = "#c22"; }
        setTimeout(() => { if (hbStatusEl) hbStatusEl.textContent = ""; }, 3000);
      }
    };
    hbModeEl?.addEventListener("change", saveHbConfig);
    hbStartEl?.addEventListener("change", saveHbConfig);
    hbEndEl?.addEventListener("change", saveHbConfig);

    // Bind profile editor
    {
      const viewEl = document.getElementById("profileView");
      const editorEl = document.getElementById("profileEditor");
      const editBtn = document.getElementById("profileEditBtn");
      const saveBtn = document.getElementById("profileSaveBtn");
      const cancelBtn = document.getElementById("profileCancelBtn");
      const statusEl = document.getElementById("profileStatus");

      editBtn?.addEventListener("click", () => {
        editorEl.value = detail.identity || "";
        viewEl.style.display = "none";
        editorEl.style.display = "block";
        editBtn.style.display = "none";
        saveBtn.style.display = "inline-block";
        cancelBtn.style.display = "inline-block";
      });

      cancelBtn?.addEventListener("click", () => {
        viewEl.style.display = "block";
        editorEl.style.display = "none";
        editBtn.style.display = "inline-block";
        saveBtn.style.display = "none";
        cancelBtn.style.display = "none";
      });

      saveBtn?.addEventListener("click", async () => {
        saveBtn.disabled = true;
        saveBtn.textContent = "保存中...";
        if (statusEl) statusEl.textContent = "";
        try {
          const resp = await fetch(`/api/animas/${encodeURIComponent(name)}/identity`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: editorEl.value }),
          });
          if (!resp.ok) throw new Error("Save failed");
          detail.identity = editorEl.value;
          viewEl.textContent = editorEl.value;
          viewEl.style.display = "block";
          editorEl.style.display = "none";
          editBtn.style.display = "inline-block";
          saveBtn.style.display = "none";
          cancelBtn.style.display = "none";
          if (statusEl) { statusEl.textContent = "✅ 保存しました"; statusEl.style.color = "#2a2"; }
          setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 3000);
        } catch (err) {
          if (statusEl) { statusEl.textContent = "❌ 保存に失敗しました"; statusEl.style.color = "#c22"; }
          setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 3000);
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = "保存";
        }
      });
    }

    // Bind trigger button
    document.getElementById("animaDetailTrigger")?.addEventListener("click", async (e) => {
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = t("animas.running");
      try {
        await fetch(`/api/animas/${encodeURIComponent(name)}/trigger`, { method: "POST" });
        btn.textContent = t("animas.success");
        setTimeout(() => { btn.textContent = t("animas.heartbeat_trigger"); btn.disabled = false; }, 2000);
      } catch {
        btn.textContent = t("animas.failed");
        setTimeout(() => { btn.textContent = t("animas.heartbeat_trigger"); btn.disabled = false; }, 2000);
      }
    });

  } catch (err) {
    content.innerHTML = `<div class="loading-placeholder">${t("animas.detail_load_failed")}: ${escapeHtml(err.message)}</div>`;
  }
}

// ── Helpers ────────────────────────────────

function _formatUptime(seconds) {
  if (!seconds || seconds < 0) return "--";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return t("animas.uptime_hm", { h, m });
  return t("animas.uptime_m", { m });
}
