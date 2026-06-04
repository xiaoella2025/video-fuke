(function () {
  const INSTALL_KEY = "fuke.activation.installId";
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const cfg = () => window.activation || {};
  const courseId = () => cfg().courseId || "25cm";
  const prefix = () => cfg().devicePrefix || "LIVE01";
  const licenseKey = (id, deviceCode) => `fuke.activation.license.${id}.${deviceCode}`;

  function base64UrlEncode(bytes) {
    let binary = "";
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function base64UrlDecode(text) {
    const normalized = text.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function getInstallId() {
    let installId = localStorage.getItem(INSTALL_KEY);
    if (installId) return installId;
    installId = crypto.randomUUID ? crypto.randomUUID() : base64UrlEncode(crypto.getRandomValues(new Uint8Array(16)));
    localStorage.setItem(INSTALL_KEY, installId);
    return installId;
  }

  async function getDeviceCode(id = courseId()) {
    const digest = await crypto.subtle.digest("SHA-256", enc.encode(`${id}:${getInstallId()}`));
    const compact = base64UrlEncode(new Uint8Array(digest)).replace(/[^A-Z0-9]/gi, "").toUpperCase().slice(0, 12);
    return `${prefix()}-${compact.slice(0, 4)}-${compact.slice(4, 8)}-${compact.slice(8, 12)}`;
  }

  async function importPublicKey(publicKey) {
    return crypto.subtle.importKey(
      "jwk",
      publicKey,
      { name: "ECDSA", namedCurve: "P-256" },
      false,
      ["verify"],
    );
  }

  async function verifyLicense(license, expectedCourseId, expectedDeviceCode, publicKey = cfg().publicKey) {
    try {
      const clean = String(license || "").trim();
      const parts = clean.split(".");
      if (parts.length !== 2 || !publicKey) return false;
      const [body, sig] = parts;
      const payload = JSON.parse(dec.decode(base64UrlDecode(body)));
      if (payload.courseId !== expectedCourseId) return false;
      if (payload.deviceCode !== expectedDeviceCode) return false;
      if (!payload.issuedAt) return false;
      const key = await importPublicKey(publicKey);
      return crypto.subtle.verify(
        { name: "ECDSA", hash: "SHA-256" },
        key,
        base64UrlDecode(sig),
        enc.encode(body),
      );
    } catch (_err) {
      return false;
    }
  }

  function showCourseShell() {
    const shell = document.querySelector("[data-course-shell]");
    if (shell) shell.hidden = false;
    document.body.classList.remove("activation-locked");
  }

  function hideCourseShell() {
    const shell = document.querySelector("[data-course-shell]");
    if (shell) shell.hidden = true;
    document.body.classList.add("activation-locked");
  }

  function showAuthorizedBadge() {
    if (document.querySelector(".activation-badge")) return;
    const header = document.querySelector(".app-header");
    if (!header) return;
    const badge = document.createElement("div");
    badge.className = "activation-badge";
    badge.textContent = "已授权学习";
    header.appendChild(badge);
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      const old = button.textContent;
      button.textContent = "已复制";
      button.classList.add("copied");
      setTimeout(() => {
        button.textContent = old;
        button.classList.remove("copied");
      }, 1400);
    } catch (_err) {
      button.textContent = "复制失败";
    }
  }

  async function hasValidStoredLicense(id, deviceCode) {
    const license = localStorage.getItem(licenseKey(id, deviceCode));
    if (!license) return false;
    return verifyLicense(license, id, deviceCode);
  }

  function renderActivationPage(deviceCode, onSubmit) {
    hideCourseShell();
    let page = document.querySelector(".activation-page");
    if (page) page.remove();
    page = document.createElement("main");
    page.className = "activation-page";
    const ecdsaTitle = cfg().title || "课程激活";
    page.innerHTML = `
      <section class="activation-panel">
        <h1>${escHtml(ecdsaTitle)}</h1>
        <p class="activation-help">请将设备码发给老师，获取本机激活码。</p>
        <label class="activation-label">本机设备码</label>
        <div class="activation-device-row">
          <code class="activation-device-code"></code>
          <button class="activation-copy" type="button">复制设备码</button>
        </div>
        <label class="activation-label" for="activation-license">激活码</label>
        <textarea id="activation-license" class="activation-input" rows="5" autocomplete="off" spellcheck="false"></textarea>
        <button class="activation-submit" type="button">激活课程</button>
        <div class="activation-message" role="status" aria-live="polite"></div>
      </section>`;
    page.querySelector(".activation-device-code").textContent = deviceCode;
    const copyButton = page.querySelector(".activation-copy");
    const input = page.querySelector(".activation-input");
    const submit = page.querySelector(".activation-submit");
    const message = page.querySelector(".activation-message");
    copyButton.addEventListener("click", () => copyText(deviceCode, copyButton));
    submit.addEventListener("click", async () => {
      message.textContent = "";
      submit.disabled = true;
      const result = await onSubmit(input.value);
      submit.disabled = false;
      if (!result.ok) {
        message.textContent = result.message;
        message.className = "activation-message error";
      }
    });
    document.body.appendChild(page);
  }

  async function init() {
    if (!cfg().enabled) {
      showCourseShell();
      return true;
    }
    const id = courseId();
    const deviceCode = await getDeviceCode(id);
    if (await hasValidStoredLicense(id, deviceCode)) {
      showCourseShell();
      showAuthorizedBadge();
      return true;
    }
    return new Promise((resolve) => {
      renderActivationPage(deviceCode, async (license) => {
        const ok = await verifyLicense(license, id, deviceCode);
        if (!ok) return { ok: false, message: "激活码无效，或不属于当前设备。" };
        localStorage.setItem(licenseKey(id, deviceCode), String(license).trim());
        const page = document.querySelector(".activation-page");
        if (page) page.remove();
        showCourseShell();
        showAuthorizedBadge();
        resolve(true);
        return { ok: true };
      });
    });
  }

  function escHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  window.FukeActivation = {
    base64UrlEncode,
    base64UrlDecode,
    getDeviceCode,
    verifyLicense,
    ready: init(),
  };
})();
