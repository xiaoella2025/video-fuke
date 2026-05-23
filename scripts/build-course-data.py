#!/usr/bin/env python3
"""
build-course-data.py  (v0.4 — DAG-driven)

Reads course-data/25cm/source.json (raw canvas export),
emits:
  - course-data/25cm/research-notes.md   (private inventory)
  - course-data/25cm/courseData.json     (sanitized; uses real connection DAG)
  - course-data/25cm/asset-manifest.json (anonymized path -> original URL)

After build, attempts to fetch every URL in the manifest into web/assets/<case>/.
Failure is non-fatal (sandbox environments may block source CDN).

Each generated subCard mirrors ONE author operation, with:
  inputs[]   — author's actual upstream node outputs (from connectionList)
  prompt     — the operation's prompt text
  outputs[]  — all URLs this operation produced (branches inline)

Reference-only nodes (uploaded photos, no model, no prompt) are surfaced as
"找参考图" subCards at the start of each pipeline, so students can see the
real photos the author started from.

No external-source identifiers leak into courseData.json.
"""
import json
import re
import time
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "course-data" / "25cm" / "source.json"
OUT_NOTES = ROOT / "course-data" / "25cm" / "research-notes.md"
OUT_DATA = ROOT / "course-data" / "25cm" / "courseData.json"
OUT_MANIFEST = ROOT / "course-data" / "25cm" / "asset-manifest.json"

CASE_ID = "25cm"
ASSET_PREFIX = f"assets/{CASE_ID}"


# ---------- JSON repair ----------

def repair_json_text(raw: str) -> str:
    # real export redacts some numeric ids as `25***` / bare `***` — make them valid strings
    raw = re.sub(r':\s*(\d+\*+)\s*([,\n}\]])', r': "\1"\2', raw)
    raw = re.sub(r':\s*\*+\s*([,\n}\]])', r': "***"\1', raw)
    raw = re.sub(r'(\n\s+)([A-Za-z_][A-Za-z0-9_]*)(":)', r'\1"\2\3', raw)
    lines = raw.split("\n"); fixed = []
    for i, line in enumerate(lines):
        s = line.rstrip(); nxt = ""
        for j in range(i + 1, len(lines)):
            if lines[j].strip(): nxt = lines[j].strip(); break
        nc = False
        if nxt.startswith('"') and ":" in nxt and s:
            last = s[-1]
            if last not in (",", "{", "[", ":") and (
                last.isdigit() or last in '"]}' or
                s.endswith("true") or s.endswith("false") or s.endswith("null")
            ):
                nc = True
        fixed.append(s + "," if nc else line)
    raw = "\n".join(fixed)
    raw = re.sub(r'(:\s*)0+(\d+)(?=\s*[,\n}\]])', r'\g<1>0', raw)
    return raw


def load_source():
    return json.loads(repair_json_text(SRC.read_text(encoding="utf-8")))


# ---------- Node normalization ----------

def parse_data(n):
    d = n.get("data")
    if isinstance(d, str):
        try: d = json.loads(d)
        except Exception: return {}
    return d or {}


def normalize_node(n):
    d = parse_data(n)
    p = d.get("params") or {}
    urls = d.get("url") or []
    if not isinstance(urls, list):
        urls = [urls] if urls else []
    settings = p.get("settings") or {}
    image_list = []
    for it in (p.get("imageList") or []):
        u = it.get("url") if isinstance(it, dict) else it
        if u:
            image_list.append(u)
    return {
        "nodeKey": n.get("nodeKey"),
        "type": n.get("type"),
        "name": n.get("name") or "",
        "model": p.get("model") or "",
        "prompt": p.get("prompt") or "",
        "urls": urls,
        "poster": d.get("poster") or "",
        "positionX": float(n.get("position", {}).get("positionX") or 0),
        "positionY": float(n.get("position", {}).get("positionY") or 0),
        "enableSound": p.get("enableSound") or settings.get("enableSound"),
        "taskStatus": (d.get("taskInfo") or {}).get("status"),
        "imageList": image_list,
        "ratio": p.get("ratio") or settings.get("ratio") or settings.get("aspectRatio") or "",
        "resolution": p.get("resolution") or settings.get("resolution") or "",
        "duration": p.get("duration") or settings.get("duration") or "",
        "modeType": p.get("modeType") or "",
    }


def node_kind(n):
    """reference | image_op | video_op | script"""
    if n["type"] == 1: return "script"
    if n["type"] == 3: return "video_op"
    # type 2: reference if no model and no prompt
    if not n["model"] and not n["prompt"]:
        return "reference"
    return "image_op"


# ---------- Asset path mapping ----------

def _slugify(s):
    s = (s or "x").lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or "x"


class AssetMap:
    def __init__(self):
        self.url_to_path = {}
        self.counters = defaultdict(int)

    def assign(self, url, step_slug, role):
        if not url: return ""
        if url in self.url_to_path: return self.url_to_path[url]
        ext = "png"
        m = re.search(r'\.(png|jpg|jpeg|webp|mp4|mov|webm)(\?|$)', url, re.I)
        if m:
            ext = m.group(1).lower()
            if ext == "jpeg": ext = "jpg"
        role_slug = _slugify(role)
        self.counters[(step_slug, role_slug)] += 1
        idx = self.counters[(step_slug, role_slug)]
        local = f"{ASSET_PREFIX}/{step_slug}/{role_slug}-{idx}.{ext}"
        self.url_to_path[url] = local
        return local

    def manifest(self):
        return {p: u for u, p in self.url_to_path.items()}


ASSETS = AssetMap()


# ---------- Tool recommendation ----------

# ---------- Tool recommendation (by task type, not by raw model) ----------

_NANO = {"name": "Nano Banana", "url": "https://nanobanana.ai/"}
_JIMENG = {"name": "即梦", "url": "https://jimeng.jianying.com/"}
_MJ = {"name": "Midjourney", "url": "https://www.midjourney.com/"}
_RUNWAY = {"name": "Runway", "url": "https://runwayml.com/"}
_VEO = {"name": "Google Veo", "url": "https://deepmind.google/technologies/veo/"}


def _tools(*specs):
    notes = ["推荐", "备选", "再备选", "再备选"]
    return [{"name": s["name"], "url": s["url"], "note": notes[i] if i < len(notes) else "备选"}
            for i, s in enumerate(specs)]


def recommend_tools(n):
    p = n["prompt"]
    if n["type"] == 3:  # video task
        return _tools(_JIMENG, _RUNWAY, _VEO)
    if "Integrate features" in p or "融合" in p:        # 角色融合脸：多参考图五官融合
        return _tools(_NANO, _JIMENG)
    if "三视图" in p:                                   # 角色三视图：单图驱动的结构化设定卡
        return _tools(_JIMENG, _NANO, _MJ)
    return _tools(_JIMENG, _MJ, _NANO)                  # 场景 image2image / 线稿 / Panorama


def recommend_tools_meta():                            # 文本任务
    return [
        {"name": "Gemini",  "url": "https://gemini.google.com/", "note": "推荐"},
        {"name": "ChatGPT", "url": "https://chatgpt.com/",       "note": "备选"},
        {"name": "Claude",  "url": "https://claude.ai/",         "note": "备选"},
    ]


# ---------- Prompt segmentation ----------

def segment_prompt(text):
    if not text or not text.strip(): return []
    parts = re.split(r"\n\s*\n", text.strip()); segs = []
    for i, part in enumerate(parts, 1):
        part = part.strip()
        if not part: continue
        first = part.splitlines()[0]
        if len(part) <= 80: label = f"段 {i}"
        else:
            head = first[:24]
            label = f"段 {i}：{head}…" if len(first) > 24 else f"段 {i}：{first}"
        segs.append({"label": label, "body": part})
    return segs



# ---------- DAG ----------

def build_dag(nodes, connections):
    by_key = {n["nodeKey"]: n for n in nodes}
    inp = defaultdict(list)
    out = defaultdict(list)
    for c in connections:
        s, t = c.get("source"), c.get("target")
        if s in by_key and t in by_key:
            inp[t].append(s); out[s].append(t)
    return by_key, inp, out


def walk_ancestors(start_key, inp, max_depth=6):
    seen = set(); stack = [(start_key, 0)]
    while stack:
        k, d = stack.pop()
        if k in seen or d > max_depth: continue
        seen.add(k)
        for prv in inp.get(k, []):
            yield prv
            stack.append((prv, d + 1))


# ---------- Sanitization ----------
# courseData.json (student-facing) must not leak any source identifiers:
# author names, platform, CDN host, or internal model names.

NAME_MAP = [("阿木", "男主角"), ("小汐", "女主角")]
LEAK_TERMS = ("libtv", "liblib", "小红书", "小紅書")

# Video model names are kept REAL — they carry teaching value and are not
# source/platform identifiers. Map internal id -> public marketing name.
VIDEO_MODEL_NAMES = {
    "star-video2":   "Seedance 2.0 VIP",
    "wanx2.7-video": "Wan 2.7",
    "wanxiang-v2-6": "Wan 2.6",
}


def public_model(m):
    if not m:
        return ""
    return VIDEO_MODEL_NAMES.get(m, m)


def scrub_text(s):
    # Only desensitize author character names. Prompt creative content
    # (style words, model names, dialogue) is preserved verbatim.
    if not isinstance(s, str) or not s:
        return s
    for a, b in NAME_MAP:
        s = s.replace(a, b)
    return s


def scrub_obj(obj):
    if isinstance(obj, str):
        t = scrub_text(obj)
        low = t.lower()
        if any(term in low for term in LEAK_TERMS):
            return ""
        return t
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    return obj


# ---------- Video param label (neutral, no platform info) ----------

def video_param_label(op):
    bits = []
    if op.get("ratio"):
        bits.append(str(op["ratio"]))
    if op.get("resolution"):
        bits.append(str(op["resolution"]))
    if op.get("duration"):
        bits.append(f"{op['duration']}s")
    if op.get("enableSound") in ("on", True, "true"):
        bits.append("带声")
    mode = {
        "text2video": "文生视频",
        "mixed2video": "图生视频 / 全能参考",
        "frames2video": "首尾帧",
    }.get(op.get("modeType"), "")
    if mode:
        bits.append(mode)
    return " · ".join(bits)


# ---------- Curated layout (explicit, confirmed node IDs) ----------
# Image scene-keyframes were confirmed by reverse-tracing each video's input
# imageList back to its producing node. Video roles (main/variant/copy/blank)
# were confirmed by the user against canvas screenshots.

CHARACTERS = [
    {
        "role": "male", "sid": "s3", "label": "男主角",
        "fusion": "1487c909-3406-4062-a20c-df7594fd9c78",
        "threeview": "cadab766-fbf7-4802-9bbb-bef53dddf3f0",
        "trials": [
            "3479c617-2d26-4c18-b813-d886b8a7ef6a",
            "23043fe4-fcf7-407d-9745-89e4a5cf2bb5",
            "374bdef0-eb5c-4936-abd7-a11b0dd175a2",
        ],
    },
    {
        "role": "female", "sid": "s4", "label": "女主角",
        "fusion": "a0c94491-4b4a-4a3a-91ff-e65eddcd9e49",
        "threeview": "8008fa73-ad23-4668-8e4e-4ceab801c350",
        "trials": [
            "3c539e7b-d009-44e4-9da9-030d17c0c29d",
            "38f1fc85-fc22-4257-acdd-438e8f50c288",
            "2aee9971-c635-4713-86b6-76e74ce32832",
            "31d5c3ac-87c6-4d54-9260-b64abb6c942d",
            "93f35ca6-809e-4db9-b37b-942980bc14b4",
            "b35234c9-f2dc-49da-b009-dcecad37ec76",
        ],
    },
]

SCENES = [
    {
        "key": "stairs_first_meet", "sid": "s5", "label": "楼梯初遇",
        "sceneGen": ["6d16d1c4-ddd1-4571-b018-ce8587a74f8e"],
        "variants": ["cede02a4-b615-4558-b048-0b9beb180ca1",
                     "0430a000-382f-413e-b06a-b79a12fae377"],
        "videos": [
            {"id": "24320f6a-4324-42ac-b431-6154656d0c7d",
             "role": "main", "title": "图生视频：楼梯对白"},
        ],
        "review": [],
    },
    {
        "key": "classroom_glance", "sid": "s6", "label": "教室偷看",
        "sceneGen": ["999fc420-3180-451a-b82b-764bae9e614d"],
        "variants": ["d35e8846-535d-4ed6-8c66-233355b96959",
                     "83f616a3-5fae-4e6c-8a04-2d317678ea67"],
        "videos": [
            {"id": "d8fb5c64-9c05-4cdf-bb54-4a78cc16b8c3",
             "role": "main", "title": "图生视频：教室偷看"},
            {"id": "16540213-20c9-43b0-9e0d-d26e2c00e681",
             "role": "copy", "title": "模型对比 / 副本"},
        ],
        "review": [],
    },
    {
        "key": "grass_earphones", "sid": "s7", "label": "草地共听耳机",
        "sceneGen": ["49ea107f-42ea-4eb5-8dd1-a65f58e5737c"],
        "variants": ["6599ac00-2e1a-4220-be77-2f6889c1b8f1",
                     "2a5d3703-49bf-4c4f-89ba-2d745e9c7d48",
                     "9566ad54-4b7f-4829-85e6-b0b4bbb9f6ca"],
        "videos": [
            {"id": "98dabe0b-478d-418d-96b3-fb92717a515a",
             "role": "main", "title": "图生视频：取下耳机"},
            {"id": "99e6ec86-c857-4cbf-bfcb-79a014b27f0b",
             "role": "copy", "title": "模型对比 / 副本"},
        ],
        "review": [],
    },
    {
        "key": "eye_contact", "sid": "s8", "label": "对视特写",
        "sceneGen": ["80688007-527f-4af8-bcaf-b879e3911b4d"],
        "variants": ["721bbc7a-a542-4e4c-8c3f-37c8e6ca43e6",
                     "eef196c0-ebe8-4b8b-ae2f-8402fffb3822",
                     "204b10dc-6cc5-49fb-865c-28936552c8e7"],
        "videos": [
            {"id": "ec853fb8-e05a-47e9-a862-d933e4d2f50e",
             "role": "main", "title": "图生视频：偷偷看对方"},
            {"id": "545ed39e-1993-4510-98f4-6e4f9653edbf",
             "role": "copy", "title": "模型对比 / 副本"},
        ],
        "review": [],
    },
    {
        "key": "seaside_bike", "sid": "s9", "label": "海边骑行",
        "sceneGen": ["e3d066bf-cd43-4dc5-8f2a-5bd10d9fd1a5",
                     "8c0c4d52-7297-4d2a-a645-03f74c261b78",
                     "409a61af-c2ed-402b-842c-ec85b60194dd"],
        "variants": ["2539d1de-2c2c-4ec8-bddc-285c99ec190f",
                     "963008a3-d00d-409f-a1d7-132b49c9ccc9",
                     "393a687a-a8fb-4b19-9cf9-b12411a7c46d",
                     "d9ab5f48-4f44-4f42-9f38-3b9cbd00311c",
                     "a00b910e-554f-485e-aeb6-96127cad1c56"],
        "videos": [
            {"id": "4c950c3b-0e0a-426e-93eb-e05925f180cf",
             "role": "main", "title": "图生视频：海边骑行"},
            {"id": "41d0f977-c4cc-4d35-9c98-50006a4a657e",
             "role": "main", "title": "图生视频：海边走"},
            {"id": "2cb9a843-a09d-4c58-badb-e0a1d3770e9c",
             "role": "copy", "title": "模型对比 / 副本（海边走）",
             "parent": "41d0f977-c4cc-4d35-9c98-50006a4a657e"},
        ],
        "review": [],
    },
    {
        "key": "stone_skip_fuji", "sid": "s10", "label": "打水漂富士山",
        "sceneGen": ["44b78d2a-0987-4608-b8c6-77672816074e",
                     "0084c3b7-1b05-4612-85e1-a2d23eec939f"],
        "variants": [],
        "videos": [],   # confirmed: no video node — flow stops at line art
        "review": [],
    },
    {
        "key": "fireworks_festival", "sid": "s11", "label": "烟花祭",
        "sceneGen": ["35d1d512-af07-4813-a72b-2c39ad518d44",
                     "0775fae8-6875-4c1d-a3cc-95340a89fdb6"],
        "variants": ["954376a5-2de4-48e8-aaf6-83aff581adc6",
                     "d1e6dd28-a132-476a-bb30-751b86d77b72",
                     "ac857550-7f09-41ab-8479-06f0a0b80645",
                     "618bf2ab-666e-4be2-a454-58d84269880d",
                     "0ca0246a-082f-4cb5-bbbe-7240df388e86",
                     "3104127a-6a02-4a46-b4f9-07415c774731"],
        "videos": [
            {"id": "dee06b26-8c78-4a0d-9ded-232d48a7061f",
             "role": "main", "title": "图生视频：浴衣看烟花"},
            {"id": "da18a429-76e5-4811-bff8-e05652bf1f1a",
             "role": "main", "title": "图生视频：邀约对白"},
            {"id": "9b47a753-6319-4cec-9c96-927a71e7dfd4",
             "role": "variant", "title": "更多变体：浴衣看烟花（机位 2）",
             "parent": "dee06b26-8c78-4a0d-9ded-232d48a7061f"},
            {"id": "1e0325af-7a1c-4123-9411-42df26cb3983",
             "role": "copy", "title": "模型对比 / 副本",
             "parent": "dee06b26-8c78-4a0d-9ded-232d48a7061f"},
        ],
        "review": [],
    },
]

# blank / unfinished node -> teacher-only review (not in student flow)
BLANK_NODES = ["26fc0e61-ac79-4584-9e96-22a8cbff1897"]


# ---------- Card builders ----------

def _outputs_for(op, step_slug, role):
    urls = list(op["urls"])
    if op["type"] == 3 and op.get("poster"):
        urls = [op["poster"]] + urls
    return [ASSETS.assign(u, step_slug, role) for u in urls if u]


def _inputs_for(op, by_key, inp, step_slug, role):
    """Prefer DAG upstream outputs; fall back to the node's own imageList
    (some ops attach reference photos directly without a connection line)."""
    urls = []
    for up_key in inp.get(op["nodeKey"], []):
        u = by_key.get(up_key)
        if not u:
            continue
        if u["type"] == 3 and u.get("poster"):
            urls.append(u["poster"])
        elif u["urls"]:
            urls.append(u["urls"][0])
    if not urls:
        urls = list(op.get("imageList") or [])
    return [ASSETS.assign(u, step_slug, role) for u in urls if u]


def build_image_card(op, by_key, inp, step_slug, *, title, desc="", variants=None):
    card = {
        "cardId": op["nodeKey"][:12],
        "kind": "image",
        "title": title,
        "desc": desc,
        "prompt": op["prompt"],
        "promptSegments": segment_prompt(op["prompt"]),
        "inputs": _inputs_for(op, by_key, inp, step_slug, "in"),
        "outputs": _outputs_for(op, step_slug, "out"),
        "tools": recommend_tools(op),
    }
    if variants:
        card["variants"] = variants
    return card


def build_variant(op, step_slug):
    return {
        "cardId": op["nodeKey"][:12],
        "title": op["name"] or "变体",
        "prompt": op["prompt"],
        "promptSegments": segment_prompt(op["prompt"]),
        "outputs": _outputs_for(op, step_slug, "var"),
    }


def build_video_card(op, by_key, inp, step_slug, *, title, desc=""):
    return {
        "cardId": op["nodeKey"][:12],
        "kind": "video",
        "title": title,
        "desc": desc,
        "modelLabel": public_model(op["model"]),
        "paramLabel": video_param_label(op),
        "prompt": op["prompt"],
        "promptSegments": segment_prompt(op["prompt"]),
        "inputs": _inputs_for(op, by_key, inp, step_slug, "vin"),
        "outputs": _outputs_for(op, step_slug, "vout"),
        "tools": recommend_tools(op),
        "modelCompare": [],
        "variants": [],
    }


def build_reference_card(ref_nodes, step_slug, *, title, desc, extra_urls=None):
    urls = []
    for r in ref_nodes:
        if r.get("poster"):
            urls.append(r["poster"])
        urls.extend(r["urls"])
    for u in (extra_urls or []):
        urls.append(u)
    seen = set(); uniq = []
    for u in urls:
        if u and u not in seen:
            seen.add(u); uniq.append(u)
    return {
        "cardId": "ref-" + step_slug,
        "kind": "reference",
        "title": title,
        "desc": desc,
        "prompt": "", "promptSegments": [], "inputs": [],
        "outputs": [ASSETS.assign(u, step_slug, "ref") for u in uniq],
        "tools": [],
    }


def collect_ref_ancestors(op_keys, inp, by_key):
    refs, seen = [], set()
    for k in op_keys:
        for ak in walk_ancestors(k, inp):
            if ak in seen:
                continue
            seen.add(ak)
            n = by_key.get(ak)
            if n and node_kind(n) == "reference":
                refs.append(n)
    out, seen2 = [], set()
    for r in refs:
        if r["nodeKey"] not in seen2:
            seen2.add(r["nodeKey"]); out.append(r)
    return out


def build_review_item(op, step_slug, *, kind_label, dws):
    """A 'why it wasn't chosen' review entry. Reason rules are conservative:
    we never invent a failure cause."""
    if dws == 0:
        reason = "没有接入下游，疑似未选用。"
    else:
        reason = "未接入后续主链路，推测为未选版本，具体原因需人工复核。"
    is_video = op["type"] == 3
    is_blank = not op["prompt"].strip()
    if is_blank:
        kind_label = "未完成节点示例"
        reason = "占位 / 未完成节点，画布上未生成内容。"
    item = {
        "cardId": op["nodeKey"][:12],
        "kind": "video" if is_video else "image",
        "kindLabel": kind_label,
        "reason": reason,
        "lesson": "",
        "promptHint": (op["prompt"][:60] + "…") if op["prompt"] else "",
        "prompt": op["prompt"],
        "outputs": _outputs_for(op, step_slug, "review"),
    }
    if is_video:
        item["modelLabel"] = public_model(op["model"])
        item["paramLabel"] = video_param_label(op)
    return item


# ---------- Skeleton meta ----------

SECTIONS = {
    "section_script":     "脚本准备",
    "section_characters": "角色准备",
    "section_scenes":     "场景准备",
    "section_shots":      "分镜训练",
}

SHOT_TECHNIQUES = {
    1:  {"key": "establishing_shot", "title": "建置镜头",      "desc": "用广角远景告诉观众『发生在哪里、什么时间』。"},
    2:  {"key": "match_cut",         "title": "动作匹配剪辑",  "desc": "前后两镜用相似的动作/形状衔接，让转场无缝。"},
    3:  {"key": "montage",           "title": "蒙太奇",        "desc": "把多个不同时空的短镜头按情绪剪到一起，压缩时间。"},
    4:  {"key": "close_up",          "title": "面部特写",      "desc": "镜头紧贴五官，把内心活动放到最大。"},
    5:  {"key": "dolly_zoom",        "title": "希区柯克变焦",   "desc": "推镜+反向变焦，背景被拉离/挤压，眩晕感。"},
    6:  {"key": "tracking_shot",     "title": "跟拍",          "desc": "摄影机跟着主体运动。"},
    7:  {"key": "shot_reverse_shot", "title": "正反打",        "desc": "对视语法：A 看 B → 切 B 看 A。"},
    8:  {"key": "steadicam",         "title": "斯坦尼康长镜头", "desc": "稳定器跟随的长镜头。"},
    9:  {"key": "rack_focus",        "title": "焦点切换",      "desc": "焦点前后挪动，引导观众注意力。"},
    10: {"key": "low_angle",         "title": "低角度仰拍",     "desc": "从下往上拍，强调高度/力量。"},
    11: {"key": "snap_zoom",         "title": "急推",          "desc": "瞬间快速推镜，情绪爆点。"},
    12: {"key": "long_take",         "title": "长镜头",        "desc": "一镜到底不切，情绪沉浸。"},
}

PRACTICE = {
    "label": "你的练习",
    "hint": "选填：可以上传你自己的起始图 / 写自己的提示词 / 上传你的结果图或视频，也可以什么都不传只按流程做。",
}


# ---------- Main ----------

def main():
    raw = load_source()
    raw_nodes = raw["data"].get("nodeList", [])
    connections = raw["data"].get("connectionList", [])
    nodes = [normalize_node(n) for n in raw_nodes]
    nodes_sorted = sorted(nodes, key=lambda n: (n["positionY"], n["positionX"]))
    by_key, inp, out = build_dag(nodes, connections)
    raw_by_key = {n.get("nodeKey"): n for n in raw_nodes}

    def N(node_id):
        return by_key.get(node_id)

    # ---- research-notes.md (private; real ids/models/urls) ----
    write_research_notes(raw, nodes, nodes_sorted, connections, inp)

    # ---- storyboard rows (from script node) ----
    sb_node = next((n for n in nodes if n["type"] == 1), None)
    storyboard_rows, story_text = [], ""
    if sb_node:
        d = parse_data(raw_by_key.get(sb_node["nodeKey"], {}))
        storyboard_rows = d.get("rows") or []
        story_text = (d.get("params") or {}).get("prompt", "")

    course_steps = []

    # s1: story
    course_steps.append({
        "id": "s1", "section": "section_script",
        "title": "完整故事（四幕原文）", "kind": "story",
        "body": story_text, "bodySegments": segment_prompt(story_text),
    })

    # s2: meta-prompt + 12-row storyboard table
    meta_prompt = (
        "你是资深短片导演 + 分镜师。\n"
        "我会给你一个完整的『四幕短故事』。请基于这个故事，输出一张 12 行的分镜表，\n"
        "用 Markdown 表格回复，列依次为：\n"
        "| 镜号 | 时长(秒) | 画面描述 | 景别 | 情绪 | 光影 | 音效/对白 |\n\n"
        "硬性要求：\n"
        "1. 全片共 12 镜，总时长 45~55 秒。\n"
        "2. 严格沿用故事原有的『起因-发展-高潮-结尾』四幕节奏。\n"
        "3. 画面描述里出现的角色只用『男主角』『女主角』指代。\n"
        "4. 景别要有变化，不要连续 3 镜都是特写。\n"
        "5. 关键情感节拍（第一次对视、靠近、表白）放在第 3/7/11 镜附近。\n"
        "6. 对白用日语并附中文翻译。\n\n"
        "故事原文：\n<在这里粘贴第 1 步的完整故事>"
    )
    course_steps.append({
        "id": "s2", "section": "section_script",
        "title": "反推元提示词 → 12 镜分镜表", "kind": "meta_prompt",
        "body": meta_prompt, "bodySegments": segment_prompt(meta_prompt),
        "tools": recommend_tools_meta(),
        "storyboardRows": [
            {
                "shotNumber": r.get("shotNumber"),
                "durationSeconds": r.get("durationSeconds"),
                "plotDescription": r.get("plotDescription", ""),
                "shotSize": r.get("shotSize", ""),
                "emotion": r.get("emotion", ""),
                "lighting": r.get("lightingAndAtmosphere", ""),
                "soundOrDialogue": r.get("audioEffects", "") or r.get("dialogue", ""),
            } for r in storyboard_rows
        ],
    })

    # s3, s4: characters
    for ch in CHARACTERS:
        step_slug = f"char-{ch['role']}"
        label = ch["label"]
        cards = []
        fusion = N(ch["fusion"])
        threeview = N(ch["threeview"])
        # 1. 找参考图 (fusion node's embedded reference photos)
        ref_urls = list(fusion.get("imageList") or []) if fusion else []
        ref_anc = collect_ref_ancestors(
            [k for k in (ch["fusion"], ch["threeview"]) if N(k)], inp, by_key)
        cards.append(build_reference_card(
            ref_anc, step_slug,
            title=f"{label} · 找参考图",
            desc="原作者放进画布的真人参考照 / 风格参考。挑你中意的同款气质即可。",
            extra_urls=ref_urls))
        # 2. 融合脸
        if fusion:
            cards.append(build_image_card(
                fusion, by_key, inp, step_slug,
                title=f"{label} · 融合脸",
                desc="把参考脸与参考体态融合，得到统一的角色基底。"))
        # 3. 三视图
        if threeview:
            cards.append(build_image_card(
                threeview, by_key, inp, step_slug,
                title=f"{label} · 三视图",
                desc="生成正/侧/背三视图角色定稿，后续所有场景都引用它。"))
        # 4. 定妆图 (milestone)
        cards.append({
            "cardId": f"milestone-{ch['role']}",
            "kind": "milestone",
            "title": f"{label} · 定妆图（你的练习）",
            "desc": "选填：挑一张你最满意的定妆图上传保存。",
            "prompt": "", "promptSegments": [], "inputs": [], "outputs": [],
            "milestoneKey": f"milestone_{ch['role']}_final",
        })
        # locked review: trial / abandoned character sheets
        review_items = []
        for tid in ch["trials"]:
            op = N(tid)
            if not op:
                continue
            dws = len(out.get(tid, []))
            kind = "融合脸（试验）" if "fusion" in classify_kind(op) else "三视图（试验）"
            review_items.append(build_review_item(op, step_slug, kind_label=kind, dws=dws))
        step = {
            "id": ch["sid"], "section": "section_characters",
            "title": label, "kind": "pipeline", "cards": cards,
            "practice": PRACTICE,
        }
        if review_items:
            step["lockedReview"] = {"title": "案例复盘：为什么没选它", "items": review_items}
        course_steps.append(step)

    # s5..s11: scenes
    for sc in SCENES:
        step_slug = f"scene-{sc['key']}"
        label = sc["label"]
        cards = []
        scene_ops = [N(i) for i in sc["sceneGen"] if N(i)]
        variant_ops = [N(i) for i in sc["variants"] if N(i)]
        # 1. 找参考图
        ref_anc = collect_ref_ancestors(
            [o["nodeKey"] for o in scene_ops], inp, by_key)
        if ref_anc:
            cards.append(build_reference_card(
                ref_anc, step_slug,
                title=f"{label} · 找参考图",
                desc="原作者用的真实参考照 / 取景截图。"))
        # 2. 场景生成 (primary keyframe) + variants attached
        var_cards = [build_variant(v, step_slug) for v in variant_ops]
        for idx, op in enumerate(scene_ops):
            attach = var_cards if idx == 0 else None
            cards.append(build_image_card(
                op, by_key, inp, step_slug,
                title=f"{label} · 场景生成" + (f"（{op['name']}）" if len(scene_ops) > 1 else ""),
                desc="image2image：用角色定稿 + 构图参考生成本场景关键帧。",
                variants=attach))
        # 3. 图生视频 (main / variant / copy)
        main_videos = [v for v in sc["videos"] if v["role"] == "main"]
        extra_videos = [v for v in sc["videos"] if v["role"] in ("variant", "copy")]
        for vi, v in enumerate(main_videos):
            op = N(v["id"])
            if not op:
                continue
            vc = build_video_card(op, by_key, inp, step_slug,
                                  title=f"{label} · {v['title']}",
                                  desc="用场景关键帧 + 角色定稿，出动态视频。")
            # attach each extra to its parent main video (parent defaults to first main)
            mine = [e for e in extra_videos
                    if e.get("parent", main_videos[0]["id"]) == v["id"]]
            course_attach_extras(vc, mine, sc, by_key, inp, step_slug)
            cards.append(vc)
        # 4. 最终结果 (milestone)
        cards.append({
            "cardId": f"milestone-scene-{sc['key']}",
            "kind": "milestone",
            "title": f"{label} · 最终结果（你的练习）",
            "desc": "选填：把你这一场景的最终图或视频上传保存。",
            "prompt": "", "promptSegments": [], "inputs": [], "outputs": [],
            "milestoneKey": f"milestone_scene_{sc['key']}",
        })
        step = {
            "id": sc["sid"], "section": "section_scenes",
            "title": label, "kind": "pipeline", "cards": cards,
            "practice": PRACTICE,
        }
        # special note for scenes without video
        if not sc["videos"]:
            step["note"] = "本场景案例画布止步于图像（线稿），未生成视频。你可在练习区自行补做视频。"
        course_steps.append(step)

    # s12..s23: 12-shot storyboard training (decoupled from canvas videos)
    for shot_n in range(1, 13):
        sid = f"s{11+shot_n}"
        row = next((r for r in storyboard_rows if r.get("shotNumber") == shot_n), None)
        cards = []
        if row:
            cards.append({
                "cardId": f"shot-{shot_n}-row",
                "kind": "storyboard",
                "title": f"第 {shot_n} 镜 · 分镜表行",
                "desc": "本镜核心参数。",
                "prompt": "", "promptSegments": [], "inputs": [], "outputs": [],
                "storyboardRow": {
                    "shotNumber": row.get("shotNumber"),
                    "durationSeconds": row.get("durationSeconds"),
                    "plotDescription": row.get("plotDescription", ""),
                    "shotSize": row.get("shotSize", ""),
                    "emotion": row.get("emotion", ""),
                    "lighting": row.get("lightingAndAtmosphere", ""),
                    "soundOrDialogue": row.get("audioEffects", "") or row.get("dialogue", ""),
                },
            })
            img_prompt = row.get("imageGenerationPrompt") or ""
            vid_prompt = row.get("videoMotionPrompt") or ""
            if img_prompt:
                cards.append({
                    "cardId": f"shot-{shot_n}-keyframe", "kind": "image",
                    "title": f"第 {shot_n} 镜 · 关键帧出图",
                    "desc": "用本镜画面 + 男女主定稿出关键帧。",
                    "prompt": img_prompt, "promptSegments": segment_prompt(img_prompt),
                    "inputs": [], "outputs": [],
                    "tools": [
                        {"name": "Nano Banana", "url": "https://nanobanana.ai/", "note": "推荐：角色一致"},
                        {"name": "Midjourney", "url": "https://www.midjourney.com/", "note": "备选"},
                    ],
                })
            if vid_prompt:
                cards.append({
                    "cardId": f"shot-{shot_n}-video", "kind": "video",
                    "title": f"第 {shot_n} 镜 · 图生视频",
                    "desc": "用关键帧 + 运动描述出 3-5 秒视频。",
                    "prompt": vid_prompt, "promptSegments": segment_prompt(vid_prompt),
                    "inputs": [], "outputs": [], "modelLabel": "", "paramLabel": "",
                    "modelCompare": [], "variants": [],
                    "tools": [
                        {"name": "Google Veo", "url": "https://deepmind.google/technologies/veo/", "note": "推荐：可带日语对白"},
                        {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选"},
                    ],
                })
        cards.append({
            "cardId": f"milestone-shot-{shot_n}", "kind": "milestone",
            "title": f"第 {shot_n} 镜 · 最终视频（你的练习）",
            "desc": "选填：把你的最终视频上传保存。",
            "prompt": "", "promptSegments": [], "inputs": [], "outputs": [],
            "milestoneKey": f"milestone_shot_{shot_n}",
        })
        tech = SHOT_TECHNIQUES.get(shot_n)
        if tech:
            cards.append({
                "cardId": f"shot-{shot_n}-knowledge", "kind": "knowledge",
                "title": "拓展知识", "desc": tech["desc"],
                "knowledgeKey": tech["key"], "knowledgeTitle": tech["title"],
                "prompt": "", "promptSegments": [], "inputs": [], "outputs": [],
            })
        course_steps.append({
            "id": sid, "section": "section_shots",
            "title": f"第 {shot_n} 镜", "kind": "pipeline", "cards": cards,
            "practice": PRACTICE,
            "note": "本镜为分镜训练项，案例画布未生成对应资产，请在练习区自行补做。",
        })

    # global teacher-only review: blank / unfinished nodes
    blank_items = []
    for bid in BLANK_NODES:
        op = N(bid)
        if op:
            blank_items.append(build_review_item(op, "blank", kind_label="未完成节点示例", dws=0))

    case_data = {
        "meta": {
            "id": CASE_ID,
            "title": "25 厘米的距离",
            "subtitle": "四幕短故事 · 角色 + 场景复刻 · 分镜训练",
            "version": "0.5.0",
            "updatedAt": "2026-05-23",
            "sections": SECTIONS,
            "labels": {
                "demo": "案例示范",
                "practice": "你的练习",
                "review": "案例复盘：为什么没选它",
            },
        },
        "steps": course_steps,
    }
    if blank_items:
        case_data["lockedReview"] = {"title": "案例复盘：为什么没选它", "items": blank_items}

    case_data = scrub_obj(case_data)
    OUT_DATA.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(ASSETS.manifest(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {OUT_DATA.relative_to(ROOT)}")
    print(f"wrote {OUT_MANIFEST.relative_to(ROOT)}  ({len(ASSETS.url_to_path)} assets)")

    fetch_assets()


def classify_kind(op):
    p = op["prompt"].lower()
    if "integrate features" in p or "融合" in op["prompt"]:
        return "fusion"
    if "三视图" in op["prompt"]:
        return "threeview"
    return "other"


def course_attach_extras(video_card, extra_videos, sc, by_key, inp, step_slug):
    for v in extra_videos:
        op = by_key.get(v["id"])
        if not op:
            continue
        entry = {
            "cardId": op["nodeKey"][:12],
            "title": v["title"],
            "modelLabel": public_model(op["model"]),
            "paramLabel": video_param_label(op),
            "prompt": op["prompt"],
            "promptSegments": segment_prompt(op["prompt"]),
            "outputs": _outputs_for(op, step_slug, "vextra"),
        }
        if v["role"] == "copy":
            video_card["modelCompare"].append(entry)
        else:
            video_card["variants"].append(entry)


def write_research_notes(raw, nodes, nodes_sorted, connections, inp):
    pm = raw["data"].get("projectMeta", {})
    lines = ["# 25 厘米的距离 · 研究笔记（私有，勿上线）", ""]
    lines.append(f"- 原始项目名：{pm.get('name','')}")
    lines.append(f"- 节点：{len(nodes)}（脚本×{sum(1 for n in nodes if n['type']==1)}"
                 f" / 图×{sum(1 for n in nodes if n['type']==2)}"
                 f" / 视频×{sum(1 for n in nodes if n['type']==3)}）")
    lines.append(f"- 连接：{len(connections)} 条")
    lines.append("")
    lines.append("## 全节点清单（按 Y 排序，含真实 nodeKey / model）")
    lines.append("")
    lines.append("| # | type | kind | name | model | urls | inputs | nodeKey | prompt |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, n in enumerate(nodes_sorted, 1):
        k = node_kind(n); ins = len(inp.get(n["nodeKey"], []))
        prm = (n["prompt"] or "").replace("\n", " ").replace("|", "/")[:60]
        lines.append(f"| {i} | {n['type']} | {k} | {n['name'][:24]} | {n['model']} | "
                     f"{len(n['urls'])} | {ins} | {n['nodeKey']} | {prm} |")
    lines.append("")
    lines.append("## 全 URL 清单（真实来源 URL）")
    lines.append("")
    for n in nodes_sorted:
        all_u = (n["urls"] or []) + ([n["poster"]] if n.get("poster") else [])
        if not all_u:
            continue
        lines.append(f"### [{n['type']}/{node_kind(n)}] {n['name']}  model={n['model']}  key={n['nodeKey']}")
        for u in all_u:
            lines.append(f"- {u}")
        lines.append("")
    OUT_NOTES.write_text("\n".join(lines), encoding="utf-8")



def fetch_assets():
    import urllib.request, ssl
    manifest = json.loads(OUT_MANIFEST.read_text(encoding="utf-8"))
    web_root = ROOT / "web"
    todo = [(p, u, web_root / p) for p, u in manifest.items()
            if not (web_root / p).exists() or (web_root / p).stat().st_size == 0]
    if not todo:
        print("[assets] all present, nothing to download"); return
    print(f"[assets] downloading {len(todo)} files...")
    ok = 0; fail = []
    ctx = ssl.create_default_context()
    for i, (lp, url, dst) in enumerate(todo, 1):
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.liblib.art/",
            })
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                data = r.read()
            if len(data) < 200: raise RuntimeError(f"too small ({len(data)}B)")
            dst.write_bytes(data); ok += 1
            print(f"  [{i}/{len(todo)}] ok  {lp}  ({len(data)//1024} KB)")
        except Exception as e:
            fail.append((lp, str(e)))
            print(f"  [{i}/{len(todo)}] FAIL {lp}  {e}")
        time.sleep(0.04)
    print(f"[assets] done: {ok} ok, {len(fail)} failed")
    if fail:
        print("[assets] re-run to retry failed downloads")


if __name__ == "__main__":
    main()
