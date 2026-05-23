/* 视频复刻教学工具 — 浅色 / 奶茶豆沙色 / 顶部段标签布局 */
(async function () {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  const STATUS_META = {
    final:      { cls: "st-final",   text: "✅ 最终采用" },
    adopted:    { cls: "st-adopted", text: "🟡 采用" },
    unused:     { cls: "st-unused",  text: "❌ 未采用" },
    trial:      { cls: "st-trial",   text: "🧪 试验稿" },
    unfinished: { cls: "st-unfin",   text: "⬜ 未完成" },
  };

  /* ---------- IndexedDB (milestone + reference uploads) ---------- */
  const DB_NAME = "fuke-uploads"; const DB_STORE = "files";
  function openDB() { return new Promise((res, rej) => {
    const r = indexedDB.open(DB_NAME, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(DB_STORE);
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  }); }
  async function dbPut(k, v) { const db = await openDB(); return new Promise((res, rej) => {
    const tx = db.transaction(DB_STORE, "readwrite"); tx.objectStore(DB_STORE).put(v, k);
    tx.oncomplete = () => res(); tx.onerror = () => rej(tx.error);
  }); }
  async function dbGet(k) { const db = await openDB(); return new Promise((res, rej) => {
    const tx = db.transaction(DB_STORE, "readonly");
    const r = tx.objectStore(DB_STORE).get(k);
    r.onsuccess = () => res(r.result || null); r.onerror = () => rej(r.error);
  }); }
  async function dbDel(k) { const db = await openDB(); return new Promise((res, rej) => {
    const tx = db.transaction(DB_STORE, "readwrite"); tx.objectStore(DB_STORE).delete(k);
    tx.oncomplete = () => res(); tx.onerror = () => rej(tx.error);
  }); }

  /* ---------- state ---------- */
  let courseData = null, courseId = null;
  let currentSection = null, currentStepId = null;
  // remember preview blob URLs so we can revoke
  const objectUrls = new Set();

  /* ---------- load case list ---------- */
  const cl = await fetch("./courses.json").then(r => r.json());
  const sel = $("#case-select");
  cl.courses.forEach(c => {
    const o = document.createElement("option");
    o.value = c.id; o.textContent = c.title; o.dataset.path = c.dataPath;
    sel.appendChild(o);
  });
  sel.addEventListener("change", () => loadCourse(sel.value));
  const lastCase = localStorage.getItem("fuke.case") || cl.courses[0].id;
  sel.value = lastCase;
  await loadCourse(sel.value);

  async function loadCourse(id) {
    localStorage.setItem("fuke.case", id);
    courseId = id;
    const path = sel.options[sel.selectedIndex].dataset.path;
    courseData = await fetch(path).then(r => r.json());
    renderCasePreview();
    renderSectionTabs();
    // pick section/step from localStorage or defaults
    const lastSec = localStorage.getItem(`fuke.section.${id}`) || Object.keys(courseData.meta.sections)[0];
    selectSection(lastSec);
    const lastStep = localStorage.getItem(`fuke.step.${id}`);
    const stepsInSec = courseData.steps.filter(s => s.section === currentSection);
    const target = (stepsInSec.find(s => s.id === lastStep) || stepsInSec[0]).id;
    showStep(target);
  }

  /* ---------- case preview video ---------- */
  function renderCasePreview() {
    const el = document.getElementById("case-preview");
    if (!el) return;
    el.innerHTML = "";
    const vidPath = "./assets/cases/live-video-01/preview/case-preview.mp4";
    const wrap = document.createElement("div"); wrap.className = "case-preview-inner";
    const lbl = document.createElement("div"); lbl.className = "case-preview-label"; lbl.textContent = "拆解的案例视频";
    wrap.appendChild(lbl);
    const v = document.createElement("video");
    v.src = vidPath; v.controls = true; v.preload = "metadata";
    v.addEventListener("error", () => {
      v.remove();
      const ph = document.createElement("div"); ph.className = "case-preview-ph";
      ph.textContent = "案例视频待上传";
      wrap.appendChild(ph);
    });
    wrap.appendChild(v);
    el.appendChild(wrap);
  }

  /* ---------- section tabs ---------- */
  function renderSectionTabs() {
    const root = $("#section-tabs");
    root.innerHTML = "";
    const sections = courseData.meta.sections;
    const counts = {};
    courseData.steps.forEach(s => { counts[s.section] = (counts[s.section] || 0) + 1; });
    Object.entries(sections).forEach(([key, label], i) => {
      const btn = document.createElement("button");
      btn.className = "section-tab"; btn.dataset.section = key;
      btn.innerHTML = `<span class="tab-no">${i+1}</span><span class="tab-label">${esc(label)}</span><span class="tab-count">${counts[key] || 0} 步</span>`;
      btn.addEventListener("click", () => {
        selectSection(key);
        const first = courseData.steps.find(s => s.section === key);
        if (first) showStep(first.id);
      });
      root.appendChild(btn);
    });
  }

  function selectSection(key) {
    currentSection = key;
    localStorage.setItem(`fuke.section.${courseId}`, key);
    $$(".section-tab").forEach(b => b.classList.toggle("active", b.dataset.section === key));
    renderStepStrip();
  }

  /* ---------- step strip (horizontal under tabs) ---------- */
  function renderStepStrip() {
    const root = $("#step-strip");
    root.innerHTML = "";
    const stepsInSec = courseData.steps.filter(s => s.section === currentSection);
    const totalIdx = {};
    let n = 0;
    courseData.steps.forEach(s => { n++; totalIdx[s.id] = n; });
    stepsInSec.forEach(s => {
      const a = document.createElement("button");
      a.className = "strip-step"; a.dataset.id = s.id;
      a.innerHTML = `<span class="ss-no">${totalIdx[s.id]}</span><span class="ss-title">${esc(s.title)}</span>${s.milestone ? '<span class="ss-dot" title="此步含 milestone">●</span>' : ""}`;
      a.addEventListener("click", () => showStep(s.id));
      root.appendChild(a);
    });
  }

  /* ---------- step render ---------- */
  function showStep(id) {
    currentStepId = id;
    localStorage.setItem(`fuke.step.${courseId}`, id);
    // ensure section matches
    const step = courseData.steps.find(s => s.id === id);
    if (step && step.section !== currentSection) selectSection(step.section);
    $$(".strip-step").forEach(a => a.classList.toggle("active", a.dataset.id === id));

    // revoke previous blob urls
    objectUrls.forEach(u => URL.revokeObjectURL(u)); objectUrls.clear();

    const main = $("#main"); main.innerHTML = "";
    if (!step) { main.innerHTML = '<div class="empty">未找到该步骤。</div>'; return; }

    const head = document.createElement("header");
    head.className = "step-head";
    head.innerHTML = `<div class="breadcrumb">${esc(courseData.meta.sections[step.section])}</div>
      <h1>${esc(step.title)}</h1>`;
    main.appendChild(head);

    if (step.note) {
      const n = document.createElement("div"); n.className = "step-note";
      n.textContent = step.note; main.appendChild(n);
    }

    if (step.kind === "story") {
      main.appendChild(renderStoryCard(step));
    } else if (step.kind === "meta_prompt" || step.kind === "storyboard_meta_prompt") {
      main.appendChild(renderMetaCard(step));
      if (step.storyboardRows && step.storyboardRows.length) {
        main.appendChild(renderStoryboardTable(step.storyboardRows));
      }
    } else if (step.kind === "chains" && step.chains) {
      step.chains.forEach((ch, i) => main.appendChild(renderChain(ch, i)));
    } else if (step.kind === "shots") {
      main.appendChild(renderShot(step));
    } else {
      main.appendChild(elFromHTML('<div class="empty">本步暂无内容。</div>'));
    }

    if (step.practice) main.appendChild(renderPractice(step));

    main.scrollIntoView({behavior: "instant", block: "start"});
  }

  /* ---------- card variants ---------- */
  function renderStoryCard(step) {
    const card = document.createElement("section"); card.className = "card story-card";
    card.innerHTML = `<div class="card-head"><span class="card-title">完整四幕原文</span>
      <button class="copy-btn" type="button">复制全文</button></div>`;
    const pre = document.createElement("pre"); pre.className = "story-body";
    pre.textContent = step.body || "";
    card.appendChild(pre);
    card.appendChild(renderSegments(step.bodySegments || []));
    card.querySelector(".copy-btn").addEventListener("click", e => copy(step.body || "", e.currentTarget));
    return card;
  }

  function renderMetaCard(step) {
    const card = document.createElement("section"); card.className = "card";
    card.innerHTML = `<div class="card-head">
      <span class="card-title">元提示词（复制后粘贴到 Gemini / ChatGPT / Claude）</span>
      <button class="copy-btn" type="button">复制全文</button></div>`;
    const pre = document.createElement("pre"); pre.className = "prompt-body";
    pre.textContent = step.body || "";
    card.appendChild(pre);
    card.appendChild(renderSegments(step.bodySegments || []));
    card.appendChild(renderTools(step.tools || []));
    card.querySelector(".copy-btn").addEventListener("click", e => copy(step.body || "", e.currentTarget));
    return card;
  }

  function renderStoryboardTable(rows) {
    const card = document.createElement("section"); card.className = "card";
    const html = ['<div class="card-head"><span class="card-title">参考分镜表</span></div>',
      '<div class="table-wrap"><table class="sb-table"><thead><tr>'];
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

  /* ---------- horizontal chain renderer ---------- */
  function renderChain(ch, idx) {
    const card = document.createElement("section");
    card.className = "card chain-card";

    // left index badge + title
    const top = document.createElement("div"); top.className = "chain-top";
    top.innerHTML = `<span class="chain-no">链路 ${idx + 1}</span>`
      + (ch.title ? `<span class="chain-title">${esc(ch.title)}</span>` : "");
    card.appendChild(top);

    // the horizontal track: cells separated by arrows, status at the end
    const track = document.createElement("div"); track.className = "chain-track";
    (ch.cells || []).forEach((cell, i) => {
      if (i > 0) track.appendChild(arrowEl());
      track.appendChild(renderCell(cell));
    });
    track.appendChild(arrowEl());
    track.appendChild(renderStatusCell(ch));
    card.appendChild(track);

    // meta row: 原模型 / 推荐模型 / 推荐参数 / 学习术语
    card.appendChild(renderChainMeta(ch));
    return card;
  }

  function arrowEl() {
    const a = document.createElement("div"); a.className = "chain-arrow"; a.textContent = "→";
    return a;
  }

  function renderCell(cell) {
    if (cell.type === "inputs") {
      const c = document.createElement("div"); c.className = "cell cell-inputs";
      const imgs = cell.images || [];
      if (!imgs.length) {
        c.appendChild(elFromHTML('<div class="ph-empty">（无输入）</div>'));
      } else {
        imgs.forEach(p => c.appendChild(makeAssetThumb(p, false, "参考图")));
      }
      return c;
    }
    if (cell.type === "prompt") {
      const c = document.createElement("div"); c.className = "cell cell-prompt-fold";
      if (cell.prompt) {
        const d = document.createElement("details"); d.className = "prompt-fold";
        d.innerHTML = `<summary>提示词（折叠 / 复制）</summary>`;
        const pre = document.createElement("pre"); pre.className = "prompt-body";
        pre.textContent = cell.prompt;          // verbatim, never rewritten
        const btn = document.createElement("button");
        btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "一键复制";
        btn.addEventListener("click", e => copy(cell.prompt, e.currentTarget));
        d.appendChild(btn); d.appendChild(pre);
        c.appendChild(d);
      } else {
        c.appendChild(elFromHTML('<div class="ph-empty">（无提示词）</div>'));
      }
      return c;
    }
    // result
    const c = document.createElement("div"); c.className = "cell cell-result";
    if (cell.path) c.appendChild(makeAssetThumb(cell.path, cell.isVideo, cell.label || ""));
    else c.appendChild(elFromHTML(`<div class="ph-empty">（${cell.isVideo ? "视频" : "结果"}待生成）</div>`));
    if (cell.label) { const cap = document.createElement("div"); cap.className = "cell-cap"; cap.textContent = cell.label; c.appendChild(cap); }
    return c;
  }

  function renderStatusCell(ch) {
    const m = STATUS_META[ch.status] || STATUS_META.unused;
    const c = document.createElement("div"); c.className = "cell cell-status";
    c.innerHTML = `<span class="status-badge ${m.cls}">${m.text}</span>`
      + (ch.reason ? `<div class="status-reason">原因：${esc(ch.reason)}</div>` : "");
    return c;
  }

  function renderChainMeta(ch) {
    const wrap = document.createElement("div"); wrap.className = "chain-meta";
    if (ch.origModel) wrap.appendChild(metaLine("原模型", esc(ch.origModel)));
    if (ch.recommend && ch.recommend.length) {
      const rec = ch.recommend.map(r => `${esc(r.name)}（${esc(r.note)}）`).join(" / ");
      wrap.appendChild(metaLine("推荐模型", rec));
    }
    if (ch.recommendParams) wrap.appendChild(metaLine("推荐参数", esc(ch.recommendParams)));
    if (ch.terms && ch.terms.length) {
      const tags = ch.terms.map(t =>
        `<a class="term-tag" href="./wiki.html" target="_blank" rel="noopener">${esc(t)}</a>`).join("");
      wrap.appendChild(metaLine("学习术语", tags));
    }
    return wrap;
  }

  function metaLine(label, html) {
    const row = document.createElement("div"); row.className = "meta-line";
    row.innerHTML = `<span class="meta-label">${esc(label)}</span><span class="meta-value">${html}</span>`;
    return row;
  }

  /* ---------- storyboard-training step ---------- */
  function renderShot(step) {
    const card = document.createElement("section"); card.className = "card";
    const r = step.storyboardRow;
    if (r) {
      const dl = document.createElement("dl"); dl.className = "sb-row";
      [["镜号", r.shotNumber], ["时长", (r.durationSeconds ?? "") + "s"], ["画面描述", r.plotDescription],
       ["景别", r.shotSize], ["情绪", r.emotion], ["光影", r.lighting], ["音效/对白", r.soundOrDialogue]]
        .forEach(([k, v]) => {
          const dt = document.createElement("dt"); dt.textContent = k;
          const dd = document.createElement("dd"); dd.textContent = (v ?? "") === "" ? "—" : v;
          dl.appendChild(dt); dl.appendChild(dd);
        });
      card.appendChild(dl);
    }
    [["关键帧提示词", step.imagePrompt], ["视频运动提示词", step.videoPrompt]].forEach(([label, text]) => {
      if (!text) return;
      const d = document.createElement("details"); d.className = "prompt-fold";
      d.innerHTML = `<summary>${esc(label)}（折叠 / 复制）</summary>`;
      const pre = document.createElement("pre"); pre.className = "prompt-body"; pre.textContent = text;
      const btn = document.createElement("button"); btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "一键复制";
      btn.addEventListener("click", e => copy(text, e.currentTarget));
      d.appendChild(btn); d.appendChild(pre); card.appendChild(d);
    });
    if (step.knowledge) {
      const k = document.createElement("div"); k.className = "knowledge-inline";
      k.innerHTML = `<a href="./wiki.html#k-${esc(step.knowledge.key)}" target="_blank" rel="noopener">了解：${esc(step.knowledge.title)} →</a>`;
      card.appendChild(k);
    }
    return card;
  }

  /* ---------- 你的练习 (one folded block per step, all optional) ---------- */
  function renderPractice(step) {
    const det = document.createElement("details"); det.className = "card practice-fold";
    det.innerHTML = `<summary>▶ 展开我的练习（默认折叠）</summary>`;
    const body = document.createElement("div"); body.className = "practice-body";
    const baseKey = `${step.id}::practice`;
    // optional prompt
    const ta = document.createElement("textarea");
    ta.className = "practice-prompt"; ta.placeholder = "在这里写你自己的提示词（可留空）";
    const tKey = `${courseId}::${baseKey}::prompt`;
    ta.value = localStorage.getItem(tKey) || "";
    ta.addEventListener("input", () => localStorage.setItem(tKey, ta.value));
    body.appendChild(labeled("写你的提示词（选填）", ta));
    // optional uploads
    body.appendChild(labeled("上传你的起始图（选填）", makeUploadSlot(baseKey + "::start", true, "上传起始图")));
    body.appendChild(labeled("上传你的结果图 / 视频（选填）", makeUploadSlot(baseKey + "::result", true, "上传结果图 / 视频")));
    det.appendChild(body);
    return det;
  }

  function labeled(label, node) {
    const wrap = document.createElement("div"); wrap.className = "practice-field";
    const l = document.createElement("div"); l.className = "practice-flabel"; l.textContent = label;
    wrap.appendChild(l); wrap.appendChild(node);
    return wrap;
  }



  function makeAssetThumb(path, isVideo, caption) {
    const fig = document.createElement("figure"); fig.className = "asset-thumb";
    const isVid = isVideo || /\.(mp4|mov|webm)$/i.test(path);
    if (isVid) {
      const v = document.createElement("video");
      v.src = path; v.controls = true; v.preload = "metadata";
      v.addEventListener("error", () => {
        fig.classList.add("missing");
        fig.innerHTML = `<div class="missing-box"><span>视频待生成</span><small>${esc(path.split("/").pop())}</small></div>`;
      });
      fig.appendChild(v);
      return fig;
    }
    const img = document.createElement("img");
    img.loading = "lazy"; img.alt = caption || ""; img.src = path;
    img.classList.add("zoomable");
    img.addEventListener("error", () => {
      fig.classList.add("missing"); img.classList.remove("zoomable");
      fig.innerHTML = `<div class="missing-box"><span>图片待生成</span><small>${esc(path.split("/").pop())}</small></div>`;
    });
    img.addEventListener("click", () => openImageModal(path, caption || ""));
    fig.appendChild(img);
    return fig;
  }

  /* ---------- image preview modal ---------- */
  let imgModal = null;
  function ensureImgModal() {
    if (imgModal) return imgModal;
    const m = document.createElement("div");
    m.className = "img-modal"; m.hidden = true;
    m.innerHTML = `
      <div class="img-modal-overlay"></div>
      <div class="img-modal-box">
        <button class="img-modal-close" type="button" aria-label="关闭">×</button>
        <img class="img-modal-img" alt="" />
        <div class="img-modal-cap"></div>
        <div class="img-modal-actions">
          <a class="img-modal-btn img-modal-download" download>下载图片</a>
          <button class="img-modal-btn img-modal-copy" type="button">复制图片信息</button>
        </div>
      </div>`;
    document.body.appendChild(m);
    const close = () => { m.hidden = true; };
    m.querySelector(".img-modal-overlay").addEventListener("click", close);
    m.querySelector(".img-modal-close").addEventListener("click", close);
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !m.hidden) close(); });
    imgModal = m;
    return m;
  }
  function openImageModal(path, caption) {
    const m = ensureImgModal();
    const img = m.querySelector(".img-modal-img");
    const cap = m.querySelector(".img-modal-cap");
    const dl = m.querySelector(".img-modal-download");
    const cp = m.querySelector(".img-modal-copy");
    img.src = path; img.alt = caption || "";
    cap.textContent = caption || path.split("/").pop();
    dl.href = path; dl.setAttribute("download", path.split("/").pop());
    cp.textContent = "复制图片信息";
    const info = `图片：${caption || path.split("/").pop()}\n路径：${path}\n用途：可作为参考图上传到即梦 / 豆包 / Nano Banana 等工具。`;
    cp.onclick = e => copy(info, e.currentTarget);
    m.hidden = false;
  }

  function makeUploadSlot(key, multi, label) {
    const wrap = document.createElement("div"); wrap.className = "upload";
    wrap.innerHTML = `
      <label class="upload-label">${esc(label)}</label>
      <div class="upload-controls">
        <input type="file" accept="image/*,video/*" ${multi ? "multiple" : ""} />
        <button class="del-btn" type="button" hidden>清空</button>
      </div>
      <div class="upload-preview"></div>`;
    const input = wrap.querySelector("input");
    const delBtn = wrap.querySelector(".del-btn");
    const prev = wrap.querySelector(".upload-preview");

    async function refresh() {
      prev.innerHTML = "";
      const blob = await dbGet(`${courseId}::${key}`);
      delBtn.hidden = !blob;
      if (blob) {
        const url = URL.createObjectURL(blob); objectUrls.add(url);
        if (blob.type && blob.type.startsWith("video")) {
          const v = document.createElement("video"); v.src = url; v.controls = true; prev.appendChild(v);
        } else {
          const img = document.createElement("img"); img.src = url; prev.appendChild(img);
        }
      }
    }
    input.addEventListener("change", async () => {
      const f = input.files[0]; if (!f) return;
      await dbPut(`${courseId}::${key}`, f);
      input.value = ""; refresh();
    });
    delBtn.addEventListener("click", async () => {
      if (!confirm("删除已上传的产物？")) return;
      await dbDel(`${courseId}::${key}`); refresh();
    });
    refresh();
    return wrap;
  }

  /* ---------- helpers ---------- */
  function renderSegments(segs) {
    if (!segs || !segs.length) return document.createDocumentFragment();
    const wrap = document.createElement("details"); wrap.className = "segments";
    wrap.innerHTML = `<summary>按段折叠 · 共 ${segs.length} 段</summary>`;
    segs.forEach(s => {
      const row = document.createElement("div"); row.className = "seg-row";
      row.innerHTML = `<div class="seg-label">${esc(s.label)}</div><pre class="seg-body"></pre>`;
      row.querySelector("pre").textContent = s.body;
      wrap.appendChild(row);
    });
    return wrap;
  }

  function renderTools(tools) {
    const wrap = document.createElement("div"); wrap.className = "tools";
    wrap.innerHTML = '<div class="tools-label">推荐工具</div>';
    const list = document.createElement("div"); list.className = "tools-list";
    tools.forEach(t => {
      const a = document.createElement("a"); a.className = "tool-chip"; a.href = t.url; a.target = "_blank"; a.rel = "noopener";
      a.innerHTML = `<strong>${esc(t.name)}</strong>${t.note ? `<span class="note">${esc(t.note)}</span>` : ""}`;
      list.appendChild(a);
    });
    wrap.appendChild(list);
    return wrap;
  }

  function elFromHTML(h) { const t = document.createElement("template"); t.innerHTML = h.trim(); return t.content.firstChild; }

  function copy(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = "已复制 ✓"; btn.classList.add("copied");
      setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1500);
    });
  }
})();
