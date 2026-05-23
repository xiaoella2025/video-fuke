/* 视频复刻教学工具 — 浅色 / 奶茶豆沙色 / 顶部段标签布局 */
(async function () {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

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

    if (step.kind === "story") {
      main.appendChild(renderStoryCard(step));
    } else if (step.kind === "storyboard_meta_prompt") {
      main.appendChild(renderMetaCard(step));
      if (step.storyboardRows && step.storyboardRows.length) {
        main.appendChild(renderStoryboardTable(step.storyboardRows));
      }
    } else if (step.subCards && step.subCards.length) {
      step.subCards.forEach(sc => main.appendChild(renderSubCard(sc, step)));
    } else {
      main.appendChild(elFromHTML('<div class="empty">本步暂无内容。</div>'));
    }

    // jump to section nav step if anchored
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

  function renderSubCard(sc, step) {
    const card = document.createElement("section");
    card.className = "card sub-card" + (sc.milestone ? " milestone" : "") + (sc.knowledgeKey ? " knowledge" : "");

    // header
    const head = document.createElement("div"); head.className = "card-head";
    head.innerHTML = `<span class="card-title">${esc(sc.title)}</span>`;
    if (sc.prompt) {
      const btn = document.createElement("button");
      btn.className = "copy-btn"; btn.type = "button"; btn.textContent = "复制全文";
      btn.addEventListener("click", e => copy(sc.prompt, e.currentTarget));
      head.appendChild(btn);
    }
    card.appendChild(head);

    if (sc.desc) {
      const p = document.createElement("p"); p.className = "desc"; p.textContent = sc.desc;
      card.appendChild(p);
    }

    if (sc.storyboardRow) {
      const r = sc.storyboardRow;
      const dl = document.createElement("dl"); dl.className = "sb-row";
      [["镜号", r.shotNumber], ["时长", (r.durationSeconds ?? "") + "s"], ["画面描述", r.plotDescription],
       ["景别", r.shotSize], ["情绪", r.emotion], ["光影", r.lighting], ["音效/对白", r.soundOrDialogue]]
        .forEach(([k, v]) => {
          const dt = document.createElement("dt"); dt.textContent = k;
          const dd = document.createElement("dd"); dd.textContent = v || "—";
          dl.appendChild(dt); dl.appendChild(dd);
        });
      card.appendChild(dl);
    }

    if (sc.knowledgeKey) {
      const k = document.createElement("div"); k.className = "knowledge-inline";
      k.innerHTML = `<a href="./wiki.html#k-${esc(sc.knowledgeKey)}" target="_blank" rel="noopener">了解：${esc(sc.knowledgeTitle || "")} →</a>`;
      card.appendChild(k);
    }

    // 3-column body: input | prompt | output
    if ((sc.inputAssets && sc.inputAssets.length) || sc.prompt || (sc.outputAssets && sc.outputAssets.length) || sc.uploadKey) {
      const grid = document.createElement("div"); grid.className = "three-col";
      grid.appendChild(renderInputColumn(sc));
      grid.appendChild(renderPromptColumn(sc));
      grid.appendChild(renderOutputColumn(sc));
      card.appendChild(grid);
    }

    if (sc.variantAssets && sc.variantAssets.length) {
      const wrap = document.createElement("div"); wrap.className = "variants";
      wrap.innerHTML = `<div class="variants-label">更多候选</div>`;
      const grid = document.createElement("div"); grid.className = "variants-grid";
      sc.variantAssets.forEach(p => grid.appendChild(makeAssetThumb(p)));
      wrap.appendChild(grid);
      card.appendChild(wrap);
    }

    if (sc.tools && sc.tools.length) card.appendChild(renderTools(sc.tools));

    return card;
  }

  /* ---------- 3 columns ---------- */
  function renderInputColumn(sc) {
    const col = document.createElement("div"); col.className = "col col-input";
    col.innerHTML = `<div class="col-label">起始图</div>`;
    const wrap = document.createElement("div"); wrap.className = "col-body";

    // If this card has an uploadKey AND no other inputs, render upload slot here
    if (sc.uploadKey && (!sc.inputAssets || !sc.inputAssets.length)) {
      wrap.appendChild(makeUploadSlot(sc.uploadKey, sc.uploadMulti, "上传你的参考图"));
    } else if (sc.inputAssets && sc.inputAssets.length) {
      sc.inputAssets.forEach(ia => wrap.appendChild(makeInputItem(ia)));
    } else {
      const ph = document.createElement("div"); ph.className = "ph-empty"; ph.textContent = "（无）";
      wrap.appendChild(ph);
    }
    col.appendChild(wrap);
    return col;
  }

  function makeInputItem(ia) {
    const cell = document.createElement("div"); cell.className = "input-cell";
    if (ia.assetPath) {
      cell.appendChild(makeAssetThumb(ia.assetPath));
      if (ia.label) { const cap = document.createElement("div"); cap.className = "cell-cap"; cap.textContent = ia.label; cell.appendChild(cap); }
    } else if (ia.uploadKey) {
      // a saved upload from elsewhere — show preview if present, else label
      const slot = document.createElement("div"); slot.className = "ref-from-upload";
      slot.textContent = ia.placeholder || "已上传";
      cell.appendChild(slot);
      dbGet(`${courseId}::${ia.uploadKey}`).then(blob => {
        if (blob) {
          const url = URL.createObjectURL(blob); objectUrls.add(url);
          slot.innerHTML = "";
          const img = document.createElement("img"); img.src = url; img.alt = ia.placeholder || "";
          slot.appendChild(img);
          if (ia.placeholder) { const c = document.createElement("div"); c.className = "cell-cap"; c.textContent = ia.placeholder; slot.appendChild(c); }
          slot.classList.add("filled");
        }
      });
    } else if (ia.placeholder) {
      const ph = document.createElement("div"); ph.className = "ph-text"; ph.textContent = ia.placeholder; cell.appendChild(ph);
    }
    return cell;
  }

  function renderPromptColumn(sc) {
    const col = document.createElement("div"); col.className = "col col-prompt";
    col.innerHTML = `<div class="col-label">提示词</div>`;
    const body = document.createElement("div"); body.className = "col-body";
    if (sc.prompt) {
      const pre = document.createElement("pre"); pre.className = "prompt-body";
      pre.textContent = sc.prompt;
      body.appendChild(pre);
      if (sc.promptSegments && sc.promptSegments.length > 1) {
        body.appendChild(renderSegments(sc.promptSegments));
      }
    } else {
      const ph = document.createElement("div"); ph.className = "ph-empty"; ph.textContent = "（本步无提示词，直接做就行）";
      body.appendChild(ph);
    }
    col.appendChild(body);
    return col;
  }

  function renderOutputColumn(sc) {
    const col = document.createElement("div"); col.className = "col col-output";
    col.innerHTML = `<div class="col-label">结果图${sc.milestone ? "（你的产物 · milestone）" : ""}</div>`;
    const body = document.createElement("div"); body.className = "col-body";

    if (sc.outputAssets && sc.outputAssets.length) {
      const grid = document.createElement("div"); grid.className = "output-grid";
      sc.outputAssets.forEach(p => grid.appendChild(makeAssetThumb(p)));
      body.appendChild(grid);
    }
    if (sc.milestone && sc.uploadKey) {
      body.appendChild(makeUploadSlot(sc.uploadKey, false, "上传你的产物"));
    } else if (!sc.outputAssets || !sc.outputAssets.length) {
      // not milestone, no examples — placeholder
      const ph = document.createElement("div"); ph.className = "ph-empty"; ph.textContent = "（参考样例待补全）";
      body.appendChild(ph);
    }
    col.appendChild(body);
    return col;
  }

  function makeAssetThumb(path) {
    const fig = document.createElement("figure"); fig.className = "asset-thumb";
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
