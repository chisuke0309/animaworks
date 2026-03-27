// ── Pipeline Feed Page ──────────────────────
import { api } from "../modules/api.js";
import { escapeHtml } from "../modules/state.js";

const POLL_INTERVAL = 5000;
const HOURS = 8;
const MAX_EVENTS = 300;
const JOB_GAP_MS = 20 * 60 * 1000; // 20分で別ジョブ

const SHOW_TYPES = new Set([
  "message_sent", "message_received",
  "task_created", "task_updated",
  "cron_executed", "error",
]);

let _timer = null;
let _lastRenderKey = "";
let _eventsById = new Map();

export function render(container) {
  _lastRenderKey = "";
  _eventsById = new Map();
  container.innerHTML = `
    <div class="pipeline-page">
      <div class="pipeline-header">
        <h2>パイプライン</h2>
        <span class="pipeline-live-badge">
          <span class="pipeline-live-dot"></span>LIVE
        </span>
        <span class="pipeline-updated" id="plUpdated">—</span>
      </div>
      <div class="pipeline-feed" id="plFeed">
        <div class="pipeline-empty">読み込み中...</div>
      </div>
      <div class="pf-status-bar" id="plStatusBar"></div>
    </div>
    <div class="pl-detail-overlay" id="plDetailOverlay" hidden></div>
    <div class="pl-detail-panel" id="plDetailPanel" hidden>
      <div class="pl-detail-header">
        <div class="pl-detail-meta" id="plDetailMeta"></div>
        <button class="pl-detail-close" id="plDetailClose">✕</button>
      </div>
      <div class="pl-detail-body" id="plDetailBody"></div>
    </div>
  `;

  const overlay = container.querySelector("#plDetailOverlay");
  const panel   = container.querySelector("#plDetailPanel");
  const closeBtn = container.querySelector("#plDetailClose");

  const closeDetail = () => {
    overlay.hidden = true;
    panel.hidden = true;
    panel.classList.remove("pl-detail-open");
  };

  overlay.addEventListener("click", closeDetail);
  closeBtn.addEventListener("click", closeDetail);
  document.addEventListener("keydown", function onKey(e) {
    if (e.key === "Escape") closeDetail();
  });

  container.querySelector("#plFeed").addEventListener("click", e => {
    const step = e.target.closest(".pj-step[data-ev-id]");
    if (!step) return;
    const ev = _eventsById.get(step.dataset.evId);
    if (ev) _showDetail(container, ev);
  });

  _startPolling(container);
}

export function destroy() {
  if (_timer) { clearInterval(_timer); _timer = null; }
  _eventsById = new Map();
}

// ── Polling ────────────────────────────────

function _startPolling(container) {
  _poll(container);
  _timer = setInterval(() => _poll(container), POLL_INTERVAL);
}

async function _poll(container) {
  try {
    const [data, animas] = await Promise.all([
      api(`/api/activity/recent?hours=${HOURS}&grouped=false&limit=${MAX_EVENTS}`),
      api("/api/animas"),
    ]);
    const feed = container.querySelector("#plFeed");
    if (!feed) return;

    const raw = (data.events || []).filter(e => SHOW_TYPES.has(e.type));
    const events = _deduplicate(raw).sort((a, b) => a.ts.localeCompare(b.ts));
    events.forEach(ev => _eventsById.set(ev.id, ev));
    const jobs = _groupIntoJobs(events); // filter はgroupIntoJobs内で実施済み

    const key = jobs.map(j => j.id + ":" + j.steps.length + ":" + j.status).join("|");
    if (key !== _lastRenderKey) {
      _lastRenderKey = key;
      _renderFeed(feed, jobs);
    }

    const statusBar = container.querySelector("#plStatusBar");
    _updateStatusBar(statusBar, animas || []);

    const updated = container.querySelector("#plUpdated");
    if (updated) {
      const n = new Date();
      updated.textContent = `${_pad(n.getHours())}:${_pad(n.getMinutes())}:${_pad(n.getSeconds())} 更新`;
    }
  } catch (e) {
    console.error("[Pipeline]", e);
  }
}

// ── Deduplicate: message_sent + message_received の同方向ペアを1つに ──

function _deduplicate(events) {
  // message_sent と message_received が同じメッセージを送信側・受信側それぞれのanima視点で記録している。
  // from_person/to等のメタは未設定の場合があるため、内容の先頭一致のみで判定する。
  // 一致した場合は received 側を除去して sent 側を残す（intentバッジ等の情報が sent 側にある）。
  const sent = events.filter(e => e.type === "message_sent");
  const drop = new Set();

  for (const recv of events) {
    if (recv.type !== "message_received") continue;
    const rKey = (recv.summary || recv.content || "").replace(/\s+/g, "").slice(0, 30);
    if (rKey.length < 5) continue;

    for (const s of sent) {
      const sKey = (s.summary || s.content || "").replace(/\s+/g, "").slice(0, 30);
      if (rKey === sKey) {
        drop.add(recv.id);
        break;
      }
    }
  }
  return events.filter(e => !drop.has(e.id));
}

// ── Job grouping ────────────────────────────
// pipeline_id があればそれでグループ化（最優先）。
// ない旧データはユーザーメッセージ起点の時系列グルーピングにフォールバック。

function _groupIntoJobs(events) {
  const byPipelineId = new Map(); // pipeline_id → job
  const timeBased = [];           // pipeline_id なしのイベント

  // ── Pass 1: pipeline_id でグループ化 ──
  for (const ev of events) {
    const pid = ev.meta?.pipeline_id;
    if (pid) {
      if (!byPipelineId.has(pid)) {
        const ts = new Date(ev.ts).getTime();
        byPipelineId.set(pid, {
          id: pid,
          trigger: null,
          startTs: ts,
          lastTs: ts,
          steps: [],
          status: "done",
          pipeline_id: pid,
        });
      }
      const job = byPipelineId.get(pid);
      const ts = new Date(ev.ts).getTime();
      // ユーザーからのメッセージはトリガーとして扱う
      const isUserMsg =
        ev.type === "message_received" &&
        (ev.from_person === "human" || ev.from_person === "user" || ev.meta?.from === "human");
      if (isUserMsg && !job.trigger) job.trigger = ev;
      job.steps.push(ev);
      if (ts < job.startTs) job.startTs = ts;
      if (ts > job.lastTs) job.lastTs = ts;
    } else {
      timeBased.push(ev);
    }
  }

  // ── Pass 2: pipeline_id なし → 旧来の時系列グルーピング ──
  const legacyJobs = [];
  let current = null;
  for (const ev of timeBased) {
    const isUserMsg =
      ev.type === "message_received" &&
      (ev.from_person === "human" || ev.from_person === "user" || ev.meta?.from === "human");
    const isCron = ev.type === "cron_executed";
    const ts = new Date(ev.ts).getTime();

    if (isUserMsg || isCron) {
      current = { id: ev.id, trigger: ev, startTs: ts, lastTs: ts, steps: [], status: "done" };
      legacyJobs.push(current);
      continue;
    }
    if (!current) {
      current = { id: "misc-" + ev.ts, trigger: null, startTs: ts, lastTs: ts, steps: [], status: "done" };
      legacyJobs.push(current);
    }
    if (ts - current.lastTs > JOB_GAP_MS) {
      current = { id: "gap-" + ev.ts, trigger: null, startTs: ts, lastTs: ts, steps: [], status: "done" };
      legacyJobs.push(current);
    }
    current.steps.push(ev);
    current.lastTs = ts;
  }

  // ── 全ジョブを統合して整形 ──
  const allJobs = [...byPipelineId.values(), ...legacyJobs];
  const now = Date.now();
  for (const j of allJobs) {
    j.steps.sort((a, b) => a.ts.localeCompare(b.ts));
    j.status = (now - j.lastTs < 5 * 60 * 1000) ? "running" : "done";
  }

  // startTs の降順（新しい順）で返す
  return allJobs
    .filter(j => j.steps.length > 0)
    .sort((a, b) => b.startTs - a.startTs);
}

// ── Feed render ─────────────────────────────

function _renderFeed(feed, jobs) {
  if (jobs.length === 0) {
    feed.innerHTML = '<div class="pipeline-empty">アクティビティがありません</div>';
    return;
  }
  feed.innerHTML = jobs.map(j => _buildJobCard(j)).join("");
}

function _buildJobCard(job) {
  const triggerText = job.trigger
    ? (job.trigger.content || job.trigger.summary || "").split("\n")[0].replace(/^[【\s]+/, "").trim().slice(0, 100)
    : "(自動実行)";
  const ts = job.trigger ? _formatTs(job.trigger.ts) : _formatTs(job.steps[0]?.ts || "");
  const statusBadge = job.status === "running"
    ? `<span class="pj-status pj-running">実行中</span>`
    : `<span class="pj-status pj-done">完了</span>`;

  const stepsHtml = job.steps.map(ev => _buildStep(ev)).join("");

  return `
    <div class="pj-card ${job.status === "running" ? "pj-card-active" : ""}">
      <div class="pj-header">
        <span class="pj-ts">${ts}</span>
        <span class="pj-title">${escapeHtml(triggerText)}</span>
        ${statusBadge}
      </div>
      <div class="pj-steps">${stepsHtml}</div>
    </div>
  `;
}

function _buildStep(ev) {
  const intent = ev.meta?.intent || "";
  const cls = _stepClass(ev);

  // 方向
  const from = ev.anima || ev.from_person || ev.meta?.from || "";
  const to   = ev.to_person || ev.meta?.to || "";

  // 内容
  const content = ev.content || ev.summary || "";
  const text = content.split("\n")[0].replace(/^[【#*\-\s「」]+/, "").trim().slice(0, 80);

  let flowHtml = "";
  if (ev.type === "message_sent") {
    flowHtml = `${_tag(from)} <span class="pj-arrow">→</span> ${_tag(to)}
      ${intent ? `<span class="pj-badge pj-badge-${intent}">${_intentLabel(intent)}</span>` : ""}`;
  } else if (ev.type === "message_received") {
    const recvFrom = ev.from_person || ev.meta?.from || "?";
    flowHtml = `${_tag(recvFrom)} <span class="pj-arrow">→</span> ${_tag(ev.anima || "")}`;
  } else if (ev.type === "task_created") {
    flowHtml = `${_tag(from)} <span class="pj-badge pj-badge-task">タスク作成</span>`;
  } else if (ev.type === "task_updated") {
    const status = ev.meta?.status || "";
    flowHtml = `${_tag(from)} <span class="pj-badge pj-badge-task">→ ${escapeHtml(status)}</span>`;
  } else if (ev.type === "error") {
    flowHtml = `${_tag(from)} <span class="pj-badge pj-badge-error">エラー</span>`;
  } else {
    flowHtml = _tag(from);
  }

  return `
    <div class="pj-step ${cls}" data-ev-id="${escapeHtml(ev.id)}" title="クリックで詳細表示">
      <span class="pj-step-ts">${_formatTs(ev.ts)}</span>
      <div class="pj-step-flow">${flowHtml}</div>
      <div class="pj-step-text">${escapeHtml(text)}</div>
    </div>
  `;
}

function _stepClass(ev) {
  const intent = ev.meta?.intent || "";
  if (ev.type === "message_sent" && intent === "delegation") return "pj-step-delegation";
  if (ev.type === "message_sent") return "pj-step-report";
  if (ev.type === "message_received") return "pj-step-report";
  if (ev.type === "task_created") return "pj-step-task";
  if (ev.type === "task_updated") return "pj-step-task";
  if (ev.type === "error") return "pj-step-error";
  return "";
}

function _tag(name) {
  if (!name) return "";
  const cls = name.toLowerCase().replace(/[^a-z]/g, "");
  return `<span class="pf-anima-tag ${cls}">${escapeHtml(name)}</span>`;
}

function _intentLabel(i) {
  return { delegation: "委任", report: "報告", question: "質問" }[i] || i;
}

function _formatTs(iso) {
  if (!iso) return "--:--";
  const d = new Date(iso);
  return `${_pad(d.getHours())}:${_pad(d.getMinutes())}`;
}

function _pad(n) { return String(n).padStart(2, "0"); }

function _showDetail(container, ev) {
  const overlay = container.querySelector("#plDetailOverlay");
  const panel   = container.querySelector("#plDetailPanel");
  const metaEl  = container.querySelector("#plDetailMeta");
  const bodyEl  = container.querySelector("#plDetailBody");

  const from   = ev.anima || ev.from_person || ev.meta?.from || "";
  const to     = ev.to_person || ev.meta?.to || "";
  const intent = ev.meta?.intent || "";
  const ts     = ev.ts ? new Date(ev.ts).toLocaleString("ja-JP", { hour12: false }) : "";

  const flowHtml = [
    from && _tag(from),
    to   && `<span class="pj-arrow">→</span> ${_tag(to)}`,
    intent && `<span class="pj-badge pj-badge-${intent}">${_intentLabel(intent)}</span>`,
  ].filter(Boolean).join(" ");

  metaEl.innerHTML = `
    <span class="pl-detail-ts">${escapeHtml(ts)}</span>
    <span class="pl-detail-flow">${flowHtml}</span>
  `;

  const fullText = ev.content || ev.summary || "(内容なし)";
  bodyEl.textContent = fullText;

  overlay.hidden = false;
  panel.hidden = false;
  requestAnimationFrame(() => panel.classList.add("pl-detail-open"));
}

function _updateStatusBar(el, animas) {
  if (!el) return;
  el.innerHTML = animas.map(a => `
    <span class="pf-status-item">
      <span class="pf-status-dot ${a.status === "running" ? "running" : "idle"}"></span>
      <span>${escapeHtml(a.name)}</span>
    </span>
  `).join("");
}
