import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

class TestElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.parent = null;
    this.className = "";
    this.textContent = "";
    this.value = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.events = {};
    this.classSet = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => this.classSet.add(name)),
      remove: (...names) => names.forEach((name) => this.classSet.delete(name)),
      toggle: (name, force) => (force ? this.classSet.add(name) : this.classSet.delete(name)),
    };
  }

  set innerHTML(value) {
    this.innerHTMLText = value;
  }

  get innerHTML() {
    return this.innerHTMLText || "";
  }

  appendChild(child) {
    child.parent = this;
    this.children.push(child);
    return child;
  }

  remove() {
    if (!this.parent) return;
    this.parent.children = this.parent.children.filter((child) => child !== this);
  }

  addEventListener(type, handler) {
    this.events[type] = handler;
  }

  click() {
    if (this.events.click) return this.events.click({ currentTarget: this });
    return undefined;
  }

  setAttribute(name, value) {
    this[name] = value;
  }

  querySelector(selector) {
    const found = findElement(this, selector);
    if (found) return found;
    if (this.innerHTML.includes(selector.slice(1))) {
      const el = new TestElement("div");
      el.className = selector.startsWith(".") ? selector.slice(1) : "";
      this.appendChild(el);
      return el;
    }
    return null;
  }
}

function matchesSelector(el, selector) {
  if (selector === "[data-course-shell]") return Boolean(el.dataset.courseShell);
  if (selector.startsWith(".")) return String(el.className).split(/\s+/).includes(selector.slice(1));
  return false;
}

function findElement(root, selector) {
  if (matchesSelector(root, selector)) return root;
  for (const child of root.children) {
    const found = findElement(child, selector);
    if (found) return found;
  }
  return null;
}

function createTestDocument() {
  const body = new TestElement("body");
  const shell = new TestElement("div");
  shell.dataset.courseShell = true;
  const header = new TestElement("header");
  header.className = "app-header";
  body.appendChild(shell);
  shell.appendChild(header);
  return {
    body,
    createElement(tagName) { return new TestElement(tagName); },
    querySelector(selector) { return findElement(body, selector); },
  };
}

async function loadActivationHarness(config = {}, existingStorage) {
  const source = await readFile(new URL("../web/activation.js", import.meta.url), "utf8");
  const storage = existingStorage || new Map();
  let clipboardText = "";
  const context = {
    console,
    crypto: globalThis.crypto,
    atob: globalThis.atob,
    btoa: globalThis.btoa,
    TextDecoder: globalThis.TextDecoder,
    TextEncoder: globalThis.TextEncoder,
    setTimeout,
    document: createTestDocument(),
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); },
      removeItem(key) { storage.delete(key); },
    },
    location: { protocol: "http:" },
    navigator: { clipboard: { writeText: async (text) => { clipboardText = text; } } },
    window: {},
  };
  context.window = context;
  context.window.activation = {
    enabled: false,
    courseId: "25cm",
    publicKey: null,
    ...config,
  };
  vm.createContext(context);
  vm.runInContext(source, context, { filename: "activation.js" });
  return { api: context.window.FukeActivation, storage, context, getClipboardText: () => clipboardText };
}

async function createLicense(api, privateKey, payload) {
  const body = api.base64UrlEncode(new TextEncoder().encode(JSON.stringify(payload)));
  const signature = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    privateKey,
    new TextEncoder().encode(body),
  );
  return `${body}.${api.base64UrlEncode(new Uint8Array(signature))}`;
}

test("device code is stable per course and stored install id", async () => {
  const { api, storage } = await loadActivationHarness();
  const first = await api.getDeviceCode("25cm");
  const second = await api.getDeviceCode("25cm");

  assert.match(first, /^LIVE01-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/);
  assert.equal(second, first);
  assert.ok(storage.get("fuke.activation.installId"));
});

test("valid license must match course id and current device code", async () => {
  const keys = await crypto.subtle.generateKey(
    { name: "ECDSA", namedCurve: "P-256" },
    true,
    ["sign", "verify"],
  );
  const publicKey = await crypto.subtle.exportKey("jwk", keys.publicKey);
  const { api } = await loadActivationHarness({ publicKey });
  const deviceCode = await api.getDeviceCode("25cm");
  const license = await createLicense(api, keys.privateKey, {
    courseId: "25cm",
    deviceCode,
    issuedAt: "2026-05-23T00:00:00.000Z",
  });

  assert.equal(await api.verifyLicense(license, "25cm", deviceCode, publicKey), true);
  assert.equal(await api.verifyLicense(license, "other-course", deviceCode, publicKey), false);
  assert.equal(await api.verifyLicense(license, "25cm", "LIVE01-XXXX-YYYY-ZZZZ", publicKey), false);
});

test("locked course renders activation page, copies device code, activates, and survives refresh", async () => {
  const keys = await crypto.subtle.generateKey(
    { name: "ECDSA", namedCurve: "P-256" },
    true,
    ["sign", "verify"],
  );
  const publicKey = await crypto.subtle.exportKey("jwk", keys.publicKey);
  const first = await loadActivationHarness({ enabled: true, publicKey });

  await new Promise((resolve) => setTimeout(resolve, 0));
  const page = first.context.document.querySelector(".activation-page");
  const shell = first.context.document.querySelector("[data-course-shell]");
  const deviceCode = page.querySelector(".activation-device-code").textContent;
  assert.equal(shell.hidden, true);
  assert.match(deviceCode, /^LIVE01-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/);

  await page.querySelector(".activation-copy").click();
  assert.equal(first.getClipboardText(), deviceCode);

  const license = await createLicense(first.api, keys.privateKey, {
    courseId: "25cm",
    deviceCode,
    issuedAt: "2026-05-23T00:00:00.000Z",
  });
  page.querySelector(".activation-input").value = license;
  await page.querySelector(".activation-submit").click();
  await first.api.ready;

  assert.equal(shell.hidden, false);
  assert.ok(first.context.document.querySelector(".activation-badge"));

  const second = await loadActivationHarness({ enabled: true, publicKey }, first.storage);
  await second.api.ready;
  assert.equal(second.context.document.querySelector("[data-course-shell]").hidden, false);
  assert.ok(second.context.document.querySelector(".activation-badge"));
});

test("owner generator private key matches student public key", async () => {
  const ownerHtml = await readFile(new URL("../owner-tools/generate-license.html", import.meta.url), "utf8");
  const configJs = await readFile(new URL("../web/activation.config.js", import.meta.url), "utf8");
  const privateKey = vm.runInNewContext(`({${ownerHtml.match(/const PRIVATE_KEY = \{([\s\S]*?)\};/)[1]}})`);
  const publicKey = vm.runInNewContext(`({${configJs.match(/publicKey: \{([\s\S]*?)\},/)[1]}})`);
  const { api } = await loadActivationHarness({ publicKey });
  const deviceCode = await api.getDeviceCode("25cm");
  const key = await crypto.subtle.importKey(
    "jwk",
    privateKey,
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  );
  const license = await createLicense(api, key, {
    courseId: "25cm",
    deviceCode,
    issuedAt: "2026-05-23T00:00:00.000Z",
  });

  assert.equal(await api.verifyLicense(license, "25cm", deviceCode, publicKey), true);
});
