// ===== 基础配置 =====
(function () {
  const KEY = "matcher_api_base";
  const DEFAULT_BASE = "http://127.0.0.1:8000";

  function getApiBase() {
    return (localStorage.getItem(KEY) || DEFAULT_BASE).replace(/\/+$/, "");
  }

  function setApiBase(v) {
    localStorage.setItem(KEY, (v || "").trim().replace(/\/+$/, ""));
  }

  window.APP = {
    KEY,
    DEFAULT_BASE,
    getApiBase,
    setApiBase,
  };
})();

// ===== DOM工具 =====
function $(sel, root = document) {
  return root.querySelector(sel);
}
function $all(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

function escapeHtml(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function fmtBool01(v) {
  if (v === true) return "1";
  if (v === false) return "0";
  return String(v ?? "");
}

function fmtNum(v, digits = 2) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : String(v ?? "");
}

function showMsg(el, text, type = "info") {
  if (!el) return;
  el.textContent = text || "";
  el.className = `msg ${type}`;
}

// ===== 网络请求 =====
async function apiFetch(path, options = {}) {
  const base = APP.getApiBase();
  const res = await fetch(base + path, options);

  const contentType = res.headers.get("content-type") || "";
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      if (contentType.includes("application/json")) {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } else {
        detail = await res.text();
      }
    } catch (_) {}
    throw new Error(detail);
  }

  if (contentType.includes("application/json")) {
    return await res.json();
  }
  return res;
}

async function apiGet(path) {
  return apiFetch(path, { method: "GET" });
}

async function apiPost(path, body = null) {
  const headers = {};
  const opts = { method: "POST", headers };
  if (body !== null) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return apiFetch(path, opts);
}

async function apiDelete(path) {
  return apiFetch(path, { method: "DELETE" });
}

async function apiUpload(path, file, fieldName = "file") {
  const fd = new FormData();
  fd.append(fieldName, file);
  return apiFetch(path, { method: "POST", body: fd });
}

async function apiDownload(path, filenameFallback = "download.xlsx") {
  const base = APP.getApiBase();
  const res = await fetch(base + path, { method: "GET" });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } else {
        detail = await res.text();
      }
    } catch (_) {}
    throw new Error(detail);
  }

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  let filename = filenameFallback;
  const m = cd.match(/filename="?([^"]+)"?/i);
  if (m && m[1]) filename = m[1];

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ===== 表格渲染 =====
function renderTable(container, columns, rows, options = {}) {
  if (!container) return;
  const { emptyText = "暂无数据", rowActions = null } = options;

  if (!rows || rows.length === 0) {
    container.innerHTML = `<div class="empty">${escapeHtml(emptyText)}</div>`;
    return;
  }

  let ths = columns.map(c => `<th>${escapeHtml(c.label)}</th>`).join("");
  if (rowActions) ths += "<th>操作</th>";

  const trs = rows.map((row, idx) => {
    const tds = columns.map(col => {
      let v = typeof col.render === "function" ? col.render(row, idx) : row[col.key];
      if (v === null || v === undefined) v = "";
      if (col.rawHtml) {
        return `<td>${v}</td>`;
      }
      return `<td>${escapeHtml(v)}</td>`;
    }).join("");

    let actionTd = "";
    if (rowActions) {
      actionTd = `<td>${rowActions(row, idx) || ""}</td>`;
    }
    return `<tr>${tds}${actionTd}</tr>`;
  }).join("");

  container.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>${ths}</tr></thead>
        <tbody>${trs}</tbody>
      </table>
    </div>
  `;
}

// ===== 分页渲染 =====
function renderPager(container, state, onChange) {
  if (!container) return;
  const total = state.total || 0;
  const offset = state.offset || 0;
  const limit = state.limit || 20;

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  container.innerHTML = `
    <div class="pager">
      <button class="btn" data-act="prev" ${currentPage <= 1 ? "disabled" : ""}>上一页</button>
      <span>第 ${currentPage} / ${totalPages} 页（共 ${total} 条）</span>
      <button class="btn" data-act="next" ${currentPage >= totalPages ? "disabled" : ""}>下一页</button>
    </div>
  `;

  container.onclick = (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === "prev" && currentPage > 1) {
      onChange({ offset: offset - limit, limit });
    }
    if (act === "next" && currentPage < totalPages) {
      onChange({ offset: offset + limit, limit });
    }
  };
}

// ===== 通用样式注入（每页复用）=====
(function injectCommonStyles() {
  const id = "__common_styles__";
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = `
    :root{
      --bg:#f6f8fb; --card:#fff; --border:#dfe5ee; --text:#1f2937; --muted:#6b7280;
      --primary:#2563eb; --danger:#dc2626; --ok:#16a34a; --warn:#d97706;
    }
    *{box-sizing:border-box}
    body{
      margin:0; padding:16px; font-family:Arial, "Microsoft YaHei", sans-serif;
      background:var(--bg); color:var(--text);
    }
    h1,h2,h3{margin:0 0 12px}
    .page{max-width:1400px; margin:0 auto}
    .card{
      background:var(--card); border:1px solid var(--border); border-radius:10px;
      padding:14px; margin-bottom:14px;
    }
    .row{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
    .col{display:flex; flex-direction:column; gap:6px}
    .grow{flex:1}
    .btn{
      border:1px solid var(--border); background:#fff; padding:8px 12px; border-radius:8px;
      cursor:pointer;
    }
    .btn:hover{border-color:#c7d2fe}
    .btn.primary{background:var(--primary); color:#fff; border-color:var(--primary)}
    .btn.danger{background:#fff5f5; color:var(--danger); border-color:#fecaca}
    .btn.ok{background:#f0fdf4; color:var(--ok); border-color:#bbf7d0}
    .btn:disabled{cursor:not-allowed; opacity:.6}
    input[type="text"], input[type="number"], select, textarea{
      border:1px solid var(--border); border-radius:8px; padding:8px 10px; min-height:36px;
      background:#fff;
    }
    textarea{width:100%; min-height:72px; resize:vertical}
    label{font-size:12px; color:var(--muted)}
    .msg{
      padding:8px 10px; border-radius:8px; border:1px solid var(--border); margin-top:8px;
      white-space:pre-wrap;
    }
    .msg.info{background:#eff6ff; border-color:#bfdbfe}
    .msg.success{background:#f0fdf4; border-color:#bbf7d0}
    .msg.error{background:#fef2f2; border-color:#fecaca}
    .msg.warn{background:#fffbeb; border-color:#fde68a}
    .muted{color:var(--muted)}
    .badge{
      display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;
      border:1px solid var(--border); background:#fff;
    }
    .grid-2{display:grid; grid-template-columns:1fr 1fr; gap:12px}
    .grid-3{display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px}
    @media (max-width: 1000px){ .grid-2,.grid-3{grid-template-columns:1fr} }

    .table-wrap{overflow:auto; border:1px solid var(--border); border-radius:8px}
    .data-table{
      width:100%; border-collapse:collapse; font-size:13px; background:#fff;
    }
    .data-table th, .data-table td{
      border-bottom:1px solid #eef2f7; padding:8px 10px; text-align:left; vertical-align:top;
      white-space:pre-wrap;
    }
    .data-table thead th{
      position:sticky; top:0; background:#f8fafc; z-index:1;
    }
    .empty{
      color:var(--muted); padding:10px; border:1px dashed var(--border); border-radius:8px;
      background:#fff;
    }
    .pager{display:flex; gap:10px; align-items:center; margin-top:10px}
    .section-title{display:flex; align-items:center; justify-content:space-between; gap:10px}
    .stats{display:flex; gap:10px; flex-wrap:wrap}
    .stat{
      border:1px solid var(--border); border-radius:8px; padding:8px 10px; background:#fff; min-width:120px;
    }
    .stat .k{font-size:12px; color:var(--muted)}
    .stat .v{font-size:18px; font-weight:700}
    .tabs{display:flex; gap:8px; flex-wrap:wrap}
    .tab-btn.active{background:#eff6ff; border-color:#bfdbfe}
    .hidden{display:none !important}
    .mono{font-family:Consolas, Menlo, monospace}
  `;
  document.head.appendChild(style);
})();