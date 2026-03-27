import { api } from "../modules/api.js";

const GOALS_PATH = "organization/goals.md";

let _editing = false;
let _content = "";

async function load() {
  const container = document.getElementById("goals-content");
  const editArea = document.getElementById("goals-editor");
  container.innerHTML = `<div class="loading-placeholder">読み込み中...</div>`;

  try {
    const data = await api(`/api/common-knowledge/${GOALS_PATH}`);
    _content = data.content || "";
    renderView();
  } catch (e) {
    container.innerHTML = `<div class="error-msg">読み込み失敗: ${e.message}</div>`;
  }
}

function renderView() {
  const container = document.getElementById("goals-content");
  const editArea = document.getElementById("goals-editor");
  const editBtn = document.getElementById("goals-edit-btn");
  const saveBtn = document.getElementById("goals-save-btn");
  const cancelBtn = document.getElementById("goals-cancel-btn");

  container.style.display = "block";
  editArea.style.display = "none";
  editBtn.style.display = "inline-flex";
  saveBtn.style.display = "none";
  cancelBtn.style.display = "none";

  // Simple markdown → HTML（見出し・太字・表・リスト）
  container.innerHTML = markdownToHtml(_content);
  _editing = false;
}

function startEdit() {
  const container = document.getElementById("goals-content");
  const editArea = document.getElementById("goals-editor");
  const editBtn = document.getElementById("goals-edit-btn");
  const saveBtn = document.getElementById("goals-save-btn");
  const cancelBtn = document.getElementById("goals-cancel-btn");

  editArea.value = _content;
  container.style.display = "none";
  editArea.style.display = "block";
  editBtn.style.display = "none";
  saveBtn.style.display = "inline-flex";
  cancelBtn.style.display = "inline-flex";
  _editing = true;
}

async function save() {
  const editArea = document.getElementById("goals-editor");
  const saveBtn = document.getElementById("goals-save-btn");
  _content = editArea.value;
  saveBtn.textContent = "保存中...";
  saveBtn.disabled = true;
  try {
    await api(`/api/common-knowledge/${GOALS_PATH}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: _content }),
    });
    renderView();
  } catch (e) {
    alert(`保存失敗: ${e.message}`);
    saveBtn.textContent = "保存";
    saveBtn.disabled = false;
  }
}

function markdownToHtml(md) {
  let html = md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    // 見出し
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    // 太字
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // 水平線
    .replace(/^---$/gm, "<hr>")
    // テーブル（簡易）
    .replace(/^\|(.+)\|$/gm, (line) => {
      if (/^[\s|:-]+$/.test(line)) return "";
      const cells = line.split("|").filter((_, i, a) => i > 0 && i < a.length - 1);
      return "<tr>" + cells.map(c => `<td>${c.trim()}</td>`).join("") + "</tr>";
    })
    // リスト
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    // 改行
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>");

  // テーブルタグでwrap
  html = html.replace(/(<tr>.*?<\/tr>\s*)+/gs, m => `<table class="goals-table">${m}</table>`);
  // リストでwrap
  html = html.replace(/(<li>.*?<\/li>\s*)+/gs, m => `<ul>${m}</ul>`);

  return `<p>${html}</p>`;
}

export function render() {
  return `
    <div class="goals-page">
      <div class="goals-header">
        <h2>組織目標</h2>
        <div class="goals-actions">
          <button id="goals-edit-btn" class="btn btn-secondary">編集</button>
          <button id="goals-save-btn" class="btn btn-primary" style="display:none">保存</button>
          <button id="goals-cancel-btn" class="btn btn-ghost" style="display:none">キャンセル</button>
        </div>
      </div>
      <div class="goals-body">
        <div id="goals-content" class="goals-markdown"></div>
        <textarea id="goals-editor" class="goals-textarea" style="display:none"></textarea>
      </div>
    </div>
  `;
}

export function mount() {
  document.getElementById("goals-edit-btn").addEventListener("click", startEdit);
  document.getElementById("goals-save-btn").addEventListener("click", save);
  document.getElementById("goals-cancel-btn").addEventListener("click", renderView);
  load();
}
