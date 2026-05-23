(async function () {
  const STORAGE_KEY = "fuke.checkpoints.v1";

  const res = await fetch("./courseData.json");
  if (!res.ok) {
    document.getElementById("course-title").textContent = "加载 courseData.json 失败";
    return;
  }
  const data = await res.json();
  const toolMap = Object.fromEntries((data.tools || []).map((t) => [t.id, t]));

  document.getElementById("course-title").textContent = data.meta.title;
  document.getElementById("course-subtitle").textContent = data.meta.subtitle || "";
  document.getElementById("course-desc").textContent = data.meta.description || "";
  document.getElementById("course-version").textContent =
    `v${data.meta.version} · 更新于 ${data.meta.updatedAt}`;

  const toolsBar = document.getElementById("tools-bar");
  (data.tools || []).forEach((t) => {
    const a = document.createElement("a");
    a.className = "tool-chip";
    a.href = t.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.innerHTML = `<strong>${t.name}</strong> <span class="usage">${t.usage}</span>`;
    toolsBar.appendChild(a);
  });

  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");

  const stepsEl = document.getElementById("steps");
  (data.steps || []).forEach((step, idx) => {
    const card = document.createElement("section");
    card.className = "step";
    card.id = step.id;

    card.innerHTML = `
      <h2>${idx + 1}. ${step.title}</h2>
      <p class="goal">${step.goal || ""}</p>

      ${section("操作步骤", listHTML(step.instructions, "ol"))}
      ${section("需要准备的素材", listHTML(step.materials, "ul"))}
      ${step.tools && step.tools.length ? section("会用到的工具", toolsHTML(step.tools, toolMap)) : ""}
      ${step.prompts && step.prompts.length ? section("提示词（点复制 → 粘贴到对应工具）", promptsHTML(step.prompts)) : ""}
      ${section("检查点", checkpointsHTML(step.id, step.checkpoints, saved))}
    `;
    stepsEl.appendChild(card);
  });

  stepsEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".copy-btn");
    if (btn) {
      const text = btn.parentElement.parentElement.querySelector("pre").innerText;
      navigator.clipboard.writeText(text).then(() => {
        btn.classList.add("copied");
        const old = btn.textContent;
        btn.textContent = "已复制";
        setTimeout(() => {
          btn.classList.remove("copied");
          btn.textContent = old;
        }, 1500);
      });
      return;
    }
    const li = e.target.closest(".checkpoints li");
    if (li) {
      li.classList.toggle("done");
      const key = li.dataset.key;
      saved[key] = li.classList.contains("done");
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    }
  });

  function section(title, body) {
    if (!body) return "";
    return `<h3>${title}</h3>${body}`;
  }
  function listHTML(items, tag) {
    if (!items || !items.length) return "";
    return `<${tag}>${items.map((x) => `<li>${escapeHTML(x)}</li>`).join("")}</${tag}>`;
  }
  function toolsHTML(ids, map) {
    return `<div class="step-tools">${ids
      .map((id) => {
        const t = map[id];
        if (!t) return `<span class="tool-chip">${id}</span>`;
        return `<a class="tool-chip" target="_blank" rel="noopener" href="${t.url}"><strong>${t.name}</strong><span class="usage">${t.usage}</span></a>`;
      })
      .join("")}</div>`;
  }
  function promptsHTML(prompts) {
    return prompts
      .map(
        (p) => `
        <div class="prompt">
          <div class="prompt-head">
            <span class="prompt-title">${escapeHTML(p.title)}</span>
            <button class="copy-btn" type="button">复制</button>
          </div>
          <pre>${escapeHTML(p.body)}</pre>
        </div>`
      )
      .join("");
  }
  function checkpointsHTML(stepId, items, saved) {
    if (!items || !items.length) return "";
    return `<ul class="checkpoints">${items
      .map((x, i) => {
        const key = `${stepId}:${i}`;
        const done = saved[key] ? " done" : "";
        return `<li class="${done.trim()}" data-key="${key}">${escapeHTML(x)}</li>`;
      })
      .join("")}</ul>`;
  }
  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }
})();
