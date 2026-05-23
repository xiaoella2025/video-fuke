/* 视频复刻教学工具 — 浅色 / 奶茶豆沙色 / 顶部段标签布局 */
(async function () {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  /* ---------- access gate (lightweight, local only) ----------
     Two codes: a student code (main flow) and a teacher code (also unlocks
     the "案例复盘：为什么没选它" review areas). Codes are stored as sha-256
     hashes — this is light protection, not real security. Change the codes
     by replacing the hashes below (sha-256 of the plaintext code). */
  const ACCESS = {
    student: "c61a26db561ce6f5728a6ce6135e61855bc52a9c419b890c6a76c8edaade3dbe", // fuke-2025
    teacher: "6b3d4bdd2197fda72dc31ace36536222ee5c2beba99ce9dc425ee85488cfa707", // fuke-teacher-2025
  };
  let role = localStorage.getItem("fuke.role") || null; // 'student' | 'teacher'

  async function sha256hex(text) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  }

  function ensureAccess() {
    if (role === "student" || role === "teacher") return Promise.resolve();
    return new Promise(resolve => {
      const ov = document.createElement("div"); ov.className = "access-overlay";
      ov.innerHTML = `
        <div class="access-box">
          <div class="access-title">✦ 视频复刻 · 教学工具</div>
          <p class="access-hint">请输入访问码进入课程。</p>
          <input class="access-input" type="password" placeholder="访问码" autocomplete="off" />
          <button class="access-btn" type="button">进入</button>
          <div class="access-err" hidden>访问码不正确，请重试。</div>
        </div>`;
      document.body.appendChild(ov);
      const input = ov.querySelector(".access-input");
      const err = ov.querySelector(".access-err");
      async function submit() {
        const h = await sha256hex(input.value.trim());
        let r = null;
        if (h === ACCESS.teacher) r = "teacher";
        else if (h === ACCESS.student) r = "student";
        if (!r) { err.hidden = false; input.select(); return; }
        role = r; localStorage.setItem("fuke.role", r);
        ov.remove(); resolve();
      }
      ov.querySelector(".access-btn").addEventListener("click", submit);
      input.addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
      input.focus();
    });
  }

  function installRoleBadge() {
    const header = $(".app-header"); if (!header || $(".role-badge")) return;
    const badge = document.createElement("button");
    badge.type = "button"; badge.className = "role-badge";
    badge.textContent = role === "teacher" ? "老师视图 · 退出" : "学员视图 · 退出";
    badge.title = "清除身份并重新输入访问码";
    badge.addEventListener("click", () => {
      localStorage.removeItem("fuke.role"); location.reload();
    });
    header.appendChild(badge);
  }

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

  /* ---------- gate first, then load ---------- */
  await ensureAccess();
  installRoleBadge();

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
    renderSectionTabs();
    // pick section/step from localStorage or defaults
    const lastSec = localStorage.getItem(`fuke.section.${id}`) || Object.keys(courseData.meta.sections)[0];
    selectSection(lastSec);
    const lastStep = localStorage.getItem(`fuke.step.${id}`);
    const stepsInSec = courseData.steps.filter(s => s.section === currentSection);
    const target = (stepsInSec.find(s => s.id === lastStep) || stepsInSec[0]).id;
    showStep(target);
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
    } else if (step.cards && step.cards.length) {
      step.cards.forEach(c => main.appendChild(renderCard(c, step)));
    } else {
      main.appendChild(elFromHTML('<div class="empty">本步暂无内容。</div>'));
    }

    if (step.lockedReview) main.appendChild(renderLockedReview(step.lockedReview));
    // global review shown once, on the last step
    const lastId = courseData.steps[courseData.steps.length - 1].id;
    if (courseData.lockedReview && step.id === lastId) {
      main.appendChild(renderLockedReview(courseData.lockedReview));
    }

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

  /* ---------- new card renderer (cards[] schema) ---------- */
  function renderCard(c, step) {
    const kind = c.kind || "image";
    const card = document.createElement("section");
    card.className = "card sub-card"
      + (kind === "milestone" ? " milestone" : "")
      + (kind === "knowledge" ? " knowledge" : "");

    // header
    const head = document.createElement("div"); head.className = "card-head";
    head.innerHTML = `<span class="card-title">${esc(c.title || "")}</span>`;
    if (c.prompt) {
      const btn = document.createElement("button");
      btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "复制提示词";
      btn.addEventListener("click", e => copy(c.prompt, e.currentTarget));
      head.appendChild(btn);
    }
    card.appendChild(head);

    if (c.kind === "video" && (c.modelLabel || c.paramLabel)) {
      const m = document.createElement("div"); m.className = "video-meta";
      m.innerHTML = `<span class="model-chip">${esc([c.modelLabel, c.paramLabel].filter(Boolean).join(" · "))}</span>`;
      card.appendChild(m);
    }

    if (c.desc) {
      const p = document.createElement("p"); p.className = "desc"; p.textContent = c.desc;
      card.appendChild(p);
    }

    if (c.storyboardRow) { card.appendChild(renderStoryboardRow(c.storyboardRow)); }

    if (kind === "knowledge" && c.knowledgeKey) {
      const k = document.createElement("div"); k.className = "knowledge-inline";
      k.innerHTML = `<a href="./wiki.html#k-${esc(c.knowledgeKey)}" target="_blank" rel="noopener">了解：${esc(c.knowledgeTitle || "")} →</a>`;
      card.appendChild(k);
    }

    // reference card: show the reference images directly (no 3-col)
    if (kind === "reference") {
      const demoLabel = document.createElement("div"); demoLabel.className = "demo-label";
      demoLabel.textContent = (courseData.meta.labels && courseData.meta.labels.demo) || "案例示范";
      card.appendChild(demoLabel);
      const grid = document.createElement("div"); grid.className = "output-grid";
      if (c.outputs && c.outputs.length) c.outputs.forEach(p => grid.appendChild(makeAssetThumb(p)));
      else grid.appendChild(elFromHTML('<div class="ph-empty">（参考图待生成）</div>'));
      card.appendChild(grid);
    }

    // 3-column demo body: 起始图 | 提示词 | 结果图 (image / video ops)
    if (kind === "image" || kind === "video") {
      const demoLabel = document.createElement("div"); demoLabel.className = "demo-label";
      demoLabel.textContent = (courseData.meta.labels && courseData.meta.labels.demo) || "案例示范";
      card.appendChild(demoLabel);
      const grid = document.createElement("div"); grid.className = "three-col";
      grid.appendChild(colThumbs("起始图", c.inputs));
      grid.appendChild(colPrompt(c));
      grid.appendChild(colThumbs("结果图", c.outputs, c.kind === "video"));
      card.appendChild(grid);
    }

    // video extras: 更多变体 + 模型对比/副本
    if (c.variants && c.variants.length) {
      card.appendChild(renderVideoFold("更多变体", c.variants));
    }
    if (c.modelCompare && c.modelCompare.length) {
      card.appendChild(renderVideoFold("模型对比 / 副本", c.modelCompare));
    }

    if (c.tools && c.tools.length) card.appendChild(renderTools(c.tools));

    // milestone IS the practice upload
    if (kind === "milestone") {
      card.appendChild(renderPractice(step, c, { milestone: true }));
    } else if (kind === "reference") {
      card.appendChild(renderPractice(step, c, { uploadLabel: "上传你自己的参考图" }));
    } else if (kind === "image" || kind === "video") {
      card.appendChild(renderPractice(step, c, { withPrompt: true }));
    }

    return card;
  }

  function renderStoryboardRow(r) {
    const dl = document.createElement("dl"); dl.className = "sb-row";
    [["镜号", r.shotNumber], ["时长", (r.durationSeconds ?? "") + "s"], ["画面描述", r.plotDescription],
     ["景别", r.shotSize], ["情绪", r.emotion], ["光影", r.lighting], ["音效/对白", r.soundOrDialogue]]
      .forEach(([k, v]) => {
        const dt = document.createElement("dt"); dt.textContent = k;
        const dd = document.createElement("dd"); dd.textContent = (v ?? "") === "" ? "—" : v;
        dl.appendChild(dt); dl.appendChild(dd);
      });
    return dl;
  }

  function colThumbs(label, paths, isVideo) {
    const col = document.createElement("div"); col.className = "col";
    col.innerHTML = `<div class="col-label">${esc(label)}</div>`;
    const body = document.createElement("div"); body.className = "col-body";
    if (paths && paths.length) {
      const grid = document.createElement("div"); grid.className = "output-grid";
      paths.forEach(p => grid.appendChild(makeAssetThumb(p, isVideo)));
      body.appendChild(grid);
    } else {
      const ph = document.createElement("div"); ph.className = "ph-empty"; ph.textContent = "（无）";
      body.appendChild(ph);
    }
    col.appendChild(body);
    return col;
  }

  function colPrompt(c) {
    const col = document.createElement("div"); col.className = "col col-prompt";
    col.innerHTML = `<div class="col-label">提示词</div>`;
    const body = document.createElement("div"); body.className = "col-body";
    if (c.prompt) {
      const pre = document.createElement("pre"); pre.className = "prompt-body";
      pre.textContent = c.prompt;          // verbatim — never rewritten
      body.appendChild(pre);
      if (c.promptSegments && c.promptSegments.length > 1) {
        body.appendChild(renderSegments(c.promptSegments));
      }
    } else {
      const ph = document.createElement("div"); ph.className = "ph-empty"; ph.textContent = "（本步无提示词）";
      body.appendChild(ph);
    }
    col.appendChild(body);
    return col;
  }

  function renderVideoFold(label, entries) {
    const d = document.createElement("details"); d.className = "video-fold";
    d.innerHTML = `<summary>${esc(label)} · ${entries.length}</summary>`;
    entries.forEach(e => {
      const row = document.createElement("div"); row.className = "fold-row";
      const meta = [e.modelLabel, e.paramLabel].filter(Boolean).join(" · ");
      row.innerHTML = `<div class="fold-head"><span class="fold-title">${esc(e.title || "")}</span>`
        + (meta ? `<span class="model-chip">${esc(meta)}</span>` : "") + `</div>`;
      const grid = document.createElement("div"); grid.className = "output-grid";
      (e.outputs || []).forEach(p => grid.appendChild(makeAssetThumb(p, true)));
      row.appendChild(grid);
      if (e.prompt) {
        const pre = document.createElement("pre"); pre.className = "prompt-body"; pre.textContent = e.prompt;
        row.appendChild(pre);
      }
      d.appendChild(row);
    });
    return d;
  }

  /* ---------- 你的练习 (all optional) ---------- */
  function renderPractice(step, c, opts = {}) {
    const wrap = document.createElement("div"); wrap.className = "practice";
    const label = (courseData.meta.labels && courseData.meta.labels.practice) || "你的练习";
    wrap.innerHTML = `<div class="practice-label">${esc(label)}<span class="practice-hint">（选填）</span></div>`;
    const baseKey = `${step.id}::${c.cardId || c.milestoneKey || "card"}`;

    if (opts.milestone) {
      wrap.appendChild(makeUploadSlot(c.milestoneKey || baseKey, false, "上传你的最终图 / 视频"));
      return wrap;
    }
    if (opts.uploadLabel) {
      wrap.appendChild(makeUploadSlot(baseKey + "::ref", true, opts.uploadLabel));
      return wrap;
    }
    // image/video practice: optional prompt textarea + optional result upload
    if (opts.withPrompt) {
      const row = document.createElement("div"); row.className = "practice-prompt-row";
      const ta = document.createElement("textarea");
      ta.className = "practice-prompt"; ta.placeholder = "在这里写你自己的提示词（可留空）";
      const tKey = `${courseId}::${baseKey}::prompt`;
      ta.value = localStorage.getItem(tKey) || "";
      ta.addEventListener("input", () => localStorage.setItem(tKey, ta.value));
      if (c.prompt) {
        const apply = document.createElement("button");
        apply.type = "button"; apply.className = "apply-prompt-btn"; apply.textContent = "套用案例提示词";
        apply.addEventListener("click", () => { ta.value = c.prompt; localStorage.setItem(tKey, ta.value); });
        row.appendChild(apply);
      }
      row.appendChild(ta);
      wrap.appendChild(row);
    }
    wrap.appendChild(makeUploadSlot(baseKey + "::result", true, "上传你的结果图 / 视频"));
    return wrap;
  }

  /* ---------- 案例复盘：为什么没选它 (teacher-only) ---------- */
  function renderLockedReview(review) {
    const sec = document.createElement("section"); sec.className = "card locked-review";
    if (role !== "teacher") {
      sec.classList.add("locked");
      sec.innerHTML = `<div class="card-head"><span class="card-title">🔒 ${esc(review.title || "案例复盘")}</span></div>
        <p class="desc">此区为老师权限可见（失败稿 / 试验稿 / 未选版本复盘）。输入老师访问码后可展开。</p>`;
      return sec;
    }
    const d = document.createElement("details"); d.className = "review-details"; d.open = false;
    d.innerHTML = `<summary>${esc(review.title || "案例复盘")} · ${review.items.length}</summary>`;
    review.items.forEach(it => {
      const row = document.createElement("div"); row.className = "review-item";
      const meta = [it.modelLabel, it.paramLabel].filter(Boolean).join(" · ");
      row.innerHTML = `<div class="review-head"><span class="review-kind">${esc(it.kindLabel || "")}</span>`
        + (meta ? `<span class="model-chip">${esc(meta)}</span>` : "") + `</div>
        <div class="review-reason">${esc(it.reason || "")}</div>`;
      const grid = document.createElement("div"); grid.className = "output-grid";
      (it.outputs || []).forEach(p => grid.appendChild(makeAssetThumb(p, it.kind === "video")));
      row.appendChild(grid);
      if (it.promptHint) {
        const ph = document.createElement("div"); ph.className = "review-hint";
        ph.textContent = "可能的问题提示词：" + it.promptHint;
        row.appendChild(ph);
      }
      d.appendChild(row);
    });
    sec.appendChild(d);
    return sec;
  }

  function makeAssetThumb(path, isVideo) {
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
    img.loading = "lazy"; img.alt = ""; img.src = path;
    img.addEventListener("error", () => {
      fig.classList.add("missing");
      fig.innerHTML = `<div class="missing-box"><span>图片待生成</span><small>${esc(path.split("/").pop())}</small></div>`;
    });
    fig.appendChild(img);
    return fig;
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
