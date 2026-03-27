import { api } from "../modules/api.js";

let _container = null;
let _posts = [];

export async function render(container) {
    _container = container;

    container.innerHTML = `
    <div class="approvals-page">
      <div class="approvals-header">
        <h2>投稿承認</h2>
        <button id="approvalsRefreshBtn" class="approvals-refresh-btn" title="更新">🔄</button>
      </div>
      <div class="approvals-list" id="approvalsList">
        <div class="approvals-loading">読み込み中...</div>
      </div>
    </div>
  `;

    document.getElementById("approvalsRefreshBtn").addEventListener("click", loadPosts);
    await loadPosts();
}

export function destroy() {
    _container = null;
    _posts = [];
}

async function loadPosts() {
    try {
        _posts = await api("/api/approvals/posts");
        renderPostList();
    } catch (e) {
        const list = document.getElementById("approvalsList");
        if (list) list.innerHTML = `<div class="approvals-error">読み込みに失敗しました</div>`;
    }
}

function renderPostList() {
    const list = document.getElementById("approvalsList");
    if (!list) return;

    if (_posts.length === 0) {
        list.innerHTML = `<div class="approvals-empty">承認待ちの投稿はありません</div>`;
        return;
    }

    list.innerHTML = _posts.map(post => {
        const statusClass = post.status === "approved" ? "status-approved" : "status-pending";
        const statusLabel = post.status === "approved" ? "承認済み" : "承認待ち";
        const slotLabel = post.slot === "morning" ? "🌅 朝" : post.slot === "evening" ? "🌇 夕" : post.slot;
        const created = formatTs(post.created_at);
        const textPreview = escapeHtml(post.text);

        return `
      <div class="approval-card" data-id="${escapeHtml(post.id)}">
        <div class="approval-card-header">
          <div class="approval-meta">
            <span class="approval-slot">${slotLabel}</span>
            <span class="approval-status ${statusClass}">${statusLabel}</span>
            <span class="approval-anima">${escapeHtml(post.anima)}</span>
            <span class="approval-time">${created}</span>
            <span class="approval-chars">${post.char_count}文字</span>
          </div>
        </div>
        <div class="approval-card-body">
          <pre class="approval-text">${textPreview}</pre>
        </div>
        <div class="approval-card-actions">
          ${post.status !== "approved"
            ? `<button class="approval-btn approve-btn" onclick="window.__approvePost('${escapeHtml(post.id)}')">✅ 承認</button>`
            : `<span class="approval-approved-label">✅ 次回cronで投稿されます</span>`
          }
          <button class="approval-btn delete-btn" onclick="window.__deletePost('${escapeHtml(post.id)}')">🗑 削除</button>
        </div>
      </div>
    `;
    }).join("");
}

// Global handlers for inline onclick
window.__approvePost = async function (postId) {
    if (!confirm("この投稿を承認しますか？次回のcron実行時にXに投稿されます。")) return;
    try {
        await api(`/api/approvals/posts/${postId}/approve`, { method: "POST" });
        await loadPosts();
    } catch (e) {
        alert("承認に失敗しました: " + e.message);
    }
};

window.__deletePost = async function (postId) {
    if (!confirm("この投稿を削除しますか？元に戻せません。")) return;
    try {
        await api(`/api/approvals/posts/${postId}`, { method: "DELETE" });
        await loadPosts();
    } catch (e) {
        alert("削除に失敗しました: " + e.message);
    }
};

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatTs(ts) {
    if (!ts) return "";
    try {
        const d = new Date(ts);
        return d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
        return ts;
    }
}
