/* 视频复刻教学工具 — 纯静态前端 */
(async function () {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  /* -------- IndexedDB for milestone uploads -------- */
  const DB_NAME = "fuke-uploads";
  const DB_STORE = "files";
  function openDB() {
    return new Promise((res, rej) => {
      const r = indexedDB.open(DB_NAME, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(DB_STORE);
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function dbPut(key, blob) {
    const db = await openDB();
    return new Promise((res, rej) => {
      const tx = db.transaction(DB_STORE, "readwrite");
      tx.objectStore(DB_STORE).put(blob, key);
      tx.oncomplete = () => res();
      tx.onerror = () => rej(tx.error);
    });
  }
  async function dbGet(key) {
    const db = await openDB();
    return new Promise((res, rej) => {
      const tx = db.transaction(DB_STORE, "readonly");
      const r = tx.objectStore(DB_STORE).get(key);
      r.onsuccess = () => res(r.result || null);
      r.onerror = () => rej(r.error);
    });
  }
  async function dbDel(key) {
    const db = await openDB();
    return new Promise((res, rej) => {
      const tx = db.transaction(DB_STORE, "readwrite");
      tx.objectStore(DB_STORE).delete(key);
      tx.oncomplete = () => res();
      tx.onerror = () => rej(tx.error);
    });
  }

  /* -------- App state -------- */
  let courseData = null;
  let currentStepId = null;
  let courseId = null;

  /* -------- Load case list, init dropdown -------- */
  const cl = await fetch("./courses.json").then(r => r.json());
  const sel = $("#case-select");
  cl.courses.forEach(c => {
    const o = document.createElement("option");
    o.value = c.id;
    o.textContent = c.title;
    o.dataset.path = c.dataPath;
    sel.appendChild(o);
  });
  sel.addEventListener("change", () => loadCourse(sel.value));
  // pick first by default (or restore from localStorage)
  const lastCase = localStorage.getItem("fuke.case") || cl.courses[0].id;
  sel.value = lastCase;
  await loadCourse(sel.value);

  async function loadCourse(id) {
    localStorage.setItem("fuke.case", id);
    courseId = id;
    const path = sel.options[sel.selectedIndex].dataset.path;
    courseData = await fetch(path).then(r => r.json());
    renderSidebar();
    // restore last step
    const last = localStorage.getItem(`fuke.step.${id}`);
    const target = (courseData.steps.find(s => s.id === last) || courseData.steps[0]).id;
    showStep(target);
  }

  /* -------- Sidebar -------- */
  function renderSidebar() {
    const root = $("#sidebar");
    root.innerHTML = "";
    const sections = {};
    courseData.steps.forEach(s => {
      (sections[s.section] = sections[s.section] || []).push(s);
    });
    let stepIndex = 0;
    Object.entries(sections).forEach(([sectionName, steps]) => {
      const group = document.createElement("div");
      group.className = "side-group";
      const h = document.createElement("div");
      h.className = "side-group-title";
      h.textContent = sectionName;
      group.appendChild(h);
      steps.forEach(s => {
        stepIndex++;
        const a = document.createElement("a");
        a.className = "side-step";
        a.dataset.id = s.id;
        a.href = "#" + s.id;
        a.innerHTML = `<span class="step-no">${stepIndex}</span><span class="step-title">${esc(s.title)}</span>${s.milestone ? '<span class="ms-dot" title="此步有 milestone 上传">●</span>' : ""}`;
        a.addEventListener("click", (e) => { e.preventDefault(); showStep(s.id); });
        group.appendChild(a);
      });
      root.appendChild(group);
    });
  }

  /* -------- Step rendering -------- */
  function showStep(id) {
    currentStepId = id;
    localStorage.setItem(`fuke.step.${courseId}`, id);
    $$(".side-step").forEach(a => a.classList.toggle("active", a.dataset.id === id));
    const step = courseData.steps.find(s => s.id === id);
    const main = $("#main");
    main.innerHTML = "";
    if (!step) { main.innerHTML = '<div class="empty">未找到该步骤。</div>'; return; }

    const head = document.createElement("header");
    head.className = "step-head";
    head.innerHTML = `<div class="breadcrumb">${esc(step.section)}</div>
      <h1>${esc(step.title)}</h1>`;
    main.appendChild(head);

    // step.kind specific:
    if (step.kind === "story") {
      main.appendChild(renderStoryCard(step));
    } else if (step.kind === "storyboard_meta_prompt") {
      main.appendChild(renderMetaPromptCard(step));
      if (step.storyboardRows && step.storyboardRows.length) {
        main.appendChild(renderStoryboardTable(step.storyboardRows));
      }
    } else if (step.subCards && step.subCards.length) {
      step.subCards.forEach(sc => main.appendChild(renderSubCard(sc, step)));
    } else {
      main.appendChild(elFromHTML('<div class="empty">本步暂无内容。</div>'));
    }
  }

  function renderStoryCard(step) {
    const card = document.createElement("section");
    card.className = "card";
    card.innerHTML = `<div class="card-head"><span class="card-title">完整四幕原文</span>
      <button class="copy-btn" type="button">复制全文</button></div>`;
    const pre = document.createElement("pre");
    pre.className = "story-body";
    pre.textContent = step.body || "";
    card.appendChild(pre);
    card.appendChild(renderPromptSegments(step.bodySegments || []));
    card.querySelector(".copy-btn").addEventListener("click", () => copy(step.body || "", card.querySelector(".copy-btn")));
    return card;
  }

  function renderMetaPromptCard(step) {
    const card = document.createElement("section");
    card.className = "card";
    card.innerHTML = `<div class="card-head">
      <span class="card-title">元提示词（粘贴到 Gemini / ChatGPT / Claude 用）</span>
      <button class="copy-btn" type="button">复制全文</button></div>`;
    const pre = document.createElement("pre");
    pre.className = "prompt-body";
    pre.textContent = step.body || "";
    card.appendChild(pre);
    card.appendChild(renderPromptSegments(step.bodySegments || []));
    card.appendChild(renderTools(step.tools || []));
    card.querySelector(".copy-btn").addEventListener("click", () => copy(step.body || "", card.querySelector(".copy-btn")));
    return card;
  }

  function renderStoryboardTable(rows) {
    const card = document.createElement("section");
    card.className = "card";
    const html = ['<div class="card-head"><span class="card-title">参考分镜表（来自反推结果）</span></div>'];
    html.push('<div class="table-wrap"><table class="sb-table"><thead><tr>');
    ["镜号", "时长", "画面描述", "景别", "情绪", "光影", "音效/对白"].forEach(h => html.push(`<th>${h}</th>`));
    html.push("</tr></thead><tbody>");
    rows.forEach(r => {
      html.push("<tr>");
      [r.shotNumber, (r.durationSeconds ?? "") + "s", r.plotDescription, r.shotSize, r.emotion, r.lighting, r.soundOrDialogue]
        .forEach(v => html.push(`<td>${esc(v ?? "")}</td>`));
      html.push("</tr>");
    });
    html.push("</tbody></table></div>");
    card.innerHTML += html.join("");
    return card;
  }

  function renderSubCard(sc, step) {
    const card = document.createElement("section");
    card.className = "card sub-card" + (sc.milestone ? " milestone" : "");
    const head = document.createElement("div");
    head.className = "card-head";
    head.innerHTML = `<span class="card-title">${esc(sc.title)}</span>`;
    if (sc.prompt) {
      const btn = document.createElement("button");
      btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "复制全文";
      btn.addEventListener("click", () => copy(sc.prompt, btn));
      head.appendChild(btn);
    }
    card.appendChild(head);

    if (sc.desc) {
      const p = document.createElement("p");
      p.className = "desc"; p.textContent = sc.desc;
      card.appendChild(p);
    }

    if (sc.storyboardRow) {
      const r = sc.storyboardRow;
      const dl = document.createElement("dl");
      dl.className = "sb-row";
      [["镜号", r.shotNumber], ["时长", (r.durationSeconds ?? "") + "s"], ["画面描述", r.plotDescription],
       ["景别", r.shotSize], ["情绪", r.emotion], ["光影", r.lighting], ["音效/对白", r.soundOrDialogue]]
        .forEach(([k, v]) => {
          const dt = document.createElement("dt"); dt.textContent = k;
          const dd = document.createElement("dd"); dd.textContent = v || "—";
          dl.appendChild(dt); dl.appendChild(dd);
        });
      card.appendChild(dl);
    }

    if (sc.prompt) {
      const pre = document.createElement("pre");
      pre.className = "prompt-body";
      pre.textContent = sc.prompt;
      card.appendChild(pre);
      if (sc.promptSegments && sc.promptSegments.length > 1) {
        card.appendChild(renderPromptSegments(sc.promptSegments));
      }
    }

    if (sc.tools && sc.tools.length) {
      card.appendChild(renderTools(sc.tools));
    }

    if (sc.previewImages && sc.previewImages.length) {
      card.appendChild(renderPreview("参考产物", sc.previewImages));
    }
    if (sc.variantPreviews && sc.variantPreviews.length) {
      card.appendChild(renderPreview("更多变体", sc.variantPreviews));
    }

    if (sc.knowledgeKey) {
      const wrap = document.createElement("div");
      wrap.className = "knowledge-card";
      wrap.innerHTML = `<div class="kc-title">拓展知识 · <a href="./wiki.html#k-${esc(sc.knowledgeKey)}" target="_blank" rel="noopener">${esc(sc.knowledgeTitle || "查看")}</a></div>
        <div class="kc-body">${esc(sc.desc || "")}</div>`;
      card.appendChild(wrap);
    }

    if (sc.milestone && sc.uploadKey) {
      card.appendChild(renderUpload(sc.uploadKey));
    }
    return card;
  }

  function renderPromptSegments(segs) {
    if (!segs || !segs.length) return document.createDocumentFragment();
    const wrap = document.createElement("details");
    wrap.className = "segments";
    wrap.innerHTML = `<summary>按段折叠 · ${segs.length} 段（左：原文 / 注：自取）</summary>`;
    segs.forEach(s => {
      const row = document.createElement("div");
      row.className = "seg-row";
      row.innerHTML = `<div class="seg-label">${esc(s.label)}</div><pre class="seg-body">${esc(s.body)}</pre>`;
      wrap.appendChild(row);
    });
    return wrap;
  }

  function renderTools(tools) {
    const wrap = document.createElement("div");
    wrap.className = "tools";
    wrap.innerHTML = '<div class="tools-label">推荐工具</div>';
    const list = document.createElement("div");
    list.className = "tools-list";
    tools.forEach(t => {
      const a = document.createElement("a");
      a.className = "tool-chip"; a.href = t.url; a.target = "_blank"; a.rel = "noopener";
      a.innerHTML = `<strong>${esc(t.name)}</strong>${t.note ? `<span class="note">${esc(t.note)}</span>` : ""}`;
      list.appendChild(a);
    });
    wrap.appendChild(list);
    return wrap;
  }

  function renderPreview(label, urls) {
    const wrap = document.createElement("div");
    wrap.className = "preview";
    wrap.innerHTML = `<div class="preview-label">${esc(label)}</div>`;
    const grid = document.createElement("div");
    grid.className = "preview-grid";
    urls.forEach(u => {
      const img = document.createElement("img");
      img.loading = "lazy"; img.src = u;
      grid.appendChild(img);
    });
    wrap.appendChild(grid);
    return wrap;
  }

  function renderUpload(key) {
    const wrap = document.createElement("div");
    wrap.className = "upload";
    wrap.innerHTML = `
      <div class="upload-label">你的产物（milestone · 仅存本地浏览器）</div>
      <div class="upload-controls">
        <input type="file" accept="image/*,video/*" />
        <button class="del-btn" type="button" hidden>删除</button>
      </div>
      <div class="upload-preview"></div>`;
    const input = wrap.querySelector("input");
    const delBtn = wrap.querySelector(".del-btn");
    const prev = wrap.querySelector(".upload-preview");

    async function refresh() {
      const blob = await dbGet(`${courseId}::${key}`);
      prev.innerHTML = "";
      delBtn.hidden = !blob;
      if (blob) {
        const url = URL.createObjectURL(blob);
        if (blob.type && blob.type.startsWith("video")) {
          const v = document.createElement("video"); v.src = url; v.controls = true; prev.appendChild(v);
        } else {
          const img = document.createElement("img"); img.src = url; prev.appendChild(img);
        }
      }
    }
    input.addEventListener("change", async () => {
      const f = input.files[0];
      if (!f) return;
      await dbPut(`${courseId}::${key}`, f);
      input.value = "";
      refresh();
    });
    delBtn.addEventListener("click", async () => {
      if (!confirm("删除已上传的产物？")) return;
      await dbDel(`${courseId}::${key}`);
      refresh();
    });
    refresh();
    return wrap;
  }

  function elFromHTML(h) {
    const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstChild;
  }

  function copy(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = "已复制";
      btn.classList.add("copied");
      setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1500);
    });
  }
})();
