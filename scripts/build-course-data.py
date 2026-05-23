#!/usr/bin/env python3
"""
build-course-data.py

Reads course-data/25cm/source.json (raw canvas export, lightly malformed),
emits:
  - course-data/25cm/research-notes.md   (private inventory)
  - course-data/25cm/courseData.json     (sanitized, asset paths are local)
  - course-data/25cm/asset-manifest.json (path -> original URL; run fetch-assets.py to populate)

Public output never references the source platform, original author, internal
model names, or original CDN URLs.
"""
import json
import re
import hashlib
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
    raw = re.sub(r'(\n\s+)([A-Za-z_][A-Za-z0-9_]*)(":)', r'\1"\2\3', raw)
    lines = raw.split("\n")
    fixed = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        nxt = ""
        for j in range(i + 1, len(lines)):
            if lines[j].strip():
                nxt = lines[j].strip()
                break
        needs_comma = False
        if nxt.startswith('"') and ":" in nxt and stripped:
            last = stripped[-1]
            if last not in (",", "{", "[", ":"):
                if (last.isdigit() or last in '"]}'
                        or stripped.endswith("true")
                        or stripped.endswith("false")
                        or stripped.endswith("null")):
                    needs_comma = True
        fixed.append(stripped + "," if needs_comma else line)
    raw = "\n".join(fixed)
    raw = re.sub(r'(:\s*)0+(\d+)(?=\s*[,\n}\]])', r'\g<1>0', raw)
    return raw


def load_source():
    text = SRC.read_text(encoding="utf-8")
    return json.loads(repair_json_text(text))


# ---------- Node normalization ----------

def parse_data(n):
    d = n.get("data")
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except Exception:
            return {}
    return d or {}


def node_summary(n):
    d = parse_data(n)
    p = d.get("params") or {}
    urls = d.get("url") or []
    if not isinstance(urls, list):
        urls = [urls] if urls else []
    return {
        "nodeKey": n.get("nodeKey"),
        "type": n.get("type"),
        "name": n.get("name") or "",
        "model": p.get("model") or "",
        "prompt": p.get("prompt") or "",
        "urls": urls,
        "positionX": float(n.get("position", {}).get("positionX") or 0),
        "positionY": float(n.get("position", {}).get("positionY") or 0),
        "enableSound": p.get("enableSound"),
        "settings": p.get("settings") or {},
        "taskStatus": (d.get("taskInfo") or {}).get("status"),
    }


# ---------- Asset path mapping (anonymizes URLs to local paths) ----------

class AssetMap:
    def __init__(self):
        self.url_to_path = {}
        self.counters = defaultdict(int)

    def assign(self, url: str, step_slug: str, role: str) -> str:
        if url in self.url_to_path:
            return self.url_to_path[url]
        # ext detect
        ext = "png"
        m = re.search(r'\.(png|jpg|jpeg|webp|mp4|mov|webm)(\?|$)', url, re.I)
        if m:
            ext = m.group(1).lower()
            if ext == "jpeg":
                ext = "jpg"
        self.counters[(step_slug, role)] += 1
        idx = self.counters[(step_slug, role)]
        local = f"{ASSET_PREFIX}/{step_slug}/{role}-{idx}.{ext}"
        self.url_to_path[url] = local
        return local

    def assign_list(self, urls, step_slug, role):
        return [self.assign(u, step_slug, role) for u in urls]

    def manifest(self):
        return {p: u for u, p in self.url_to_path.items()}


ASSETS = AssetMap()


# ---------- Tool recommendation ----------

def recommend_tools(node):
    m = node["model"]
    p = node["prompt"]
    if m == "aurora-3-prime" or node["type"] == 1:
        return [
            {"name": "Gemini",  "url": "https://gemini.google.com/", "note": "推荐"},
            {"name": "ChatGPT", "url": "https://chatgpt.com/",       "note": "备选"},
            {"name": "Claude",  "url": "https://claude.ai/",         "note": "备选"},
        ]
    if node["type"] == 3:
        if node["enableSound"]:
            return [
                {"name": "Google Veo", "url": "https://deepmind.google/technologies/veo/", "note": "推荐：原生带声"},
                {"name": "即梦 AI",    "url": "https://jimeng.jianying.com/",              "note": "备选"},
            ]
        return [
            {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "推荐：图生视频"},
            {"name": "Runway",  "url": "https://runwayml.com/",        "note": "备选"},
        ]
    if "三视图" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/",       "note": "推荐：角色一致性"},
            {"name": "Midjourney",  "url": "https://www.midjourney.com/", "note": "备选"},
        ]
    if "Integrate features" in p or "融合" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/",       "note": "推荐：人脸融合"},
            {"name": "即梦 AI",     "url": "https://jimeng.jianying.com/", "note": "备选"},
        ]
    if "线稿" in p or "草图" in p or "Sketch" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/",       "note": "推荐：i2i 线稿"},
            {"name": "即梦 AI",     "url": "https://jimeng.jianying.com/", "note": "备选"},
        ]
    return [
        {"name": "Midjourney", "url": "https://www.midjourney.com/", "note": "推荐：电影感场景"},
        {"name": "即梦 AI",    "url": "https://jimeng.jianying.com/", "note": "备选"},
    ]


# ---------- Prompt segmentation ----------

def segment_prompt(text: str):
    if not text or not text.strip():
        return []
    parts = re.split(r"\n\s*\n", text.strip())
    segs = []
    for i, part in enumerate(parts, 1):
        part = part.strip()
        if not part:
            continue
        first_line = part.splitlines()[0]
        if len(part) <= 80:
            label = f"段 {i}"
        else:
            head = first_line[:24]
            label = f"段 {i}：{head}…" if len(first_line) > 24 else f"段 {i}：{first_line}"
        segs.append({"label": label, "body": part})
    return segs


# ---------- Classification ----------

SCENE_RULES = [
    ("stairs_first_meet",   "楼梯初遇",    ["阶梯", "汽水", "鞋柜", "玄关", "系鞋带"]),
    ("classroom_glance",    "教室偷看",    ["图书馆", "教室", "肩并肩", "偷偷看对方", "桌子上"]),
    ("grass_earphones",     "草地耳机",    ["草地", "耳机", "躺在草地", "耳朵"]),
    ("eye_contact",         "对视特写",    ["互相看着", "对视"]),
    ("seaside_bike",        "海边骑行",    ["自行车", "骑着", "骑行", "迎着海风"]),
    ("stone_skip_fuji",     "打水漂富士山", ["打水漂", "富士山"]),
    ("fireworks_festival",  "烟花祭",      ["烟花", "浴服", "花火"]),
]


def classify_scene(text: str):
    for key, label, kws in SCENE_RULES:
        for kw in kws:
            if kw in text:
                return key, label
    return None, None


def classify_image_role(node):
    p = node["prompt"]; name = node["name"]
    if "Integrate features" in p or "融合" in p:
        if "male" in p.lower() or "男" in name:
            return "char_male_fusion"
        if "female" in p.lower() or "女" in name:
            return "char_female_fusion"
        return "char_fusion"
    if "三视图" in p:
        if "男性" in p or "深色校服" in p:
            return "char_male_threeview"
        if "女性" in p or "女性校服" in p:
            return "char_female_threeview"
        return "char_threeview"
    if "线稿" in p or "草图" in p or "Sketch" in p:
        return "scene_sketch"
    k, _ = classify_scene(p + " " + name)
    if k:
        return f"scene_final::{k}"
    return "other"


# ---------- Skeleton ----------

SCENE_ORDER = [
    ("stairs_first_meet",   "楼梯初遇"),
    ("classroom_glance",    "教室偷看"),
    ("grass_earphones",     "草地共听耳机"),
    ("eye_contact",         "对视特写"),
    ("seaside_bike",        "海边骑行"),
    ("stone_skip_fuji",     "打水漂富士山"),
    ("fireworks_festival",  "烟花祭"),
]

SECTIONS = {
    "section_script":     "脚本准备",
    "section_characters": "角色准备",
    "section_scenes":     "场景准备",
    "section_shots":      "12 分镜",
}


def build_skeleton():
    steps = []
    steps.append({"id": "s1", "section": "section_script", "title": "完整故事（四幕原文）", "kind": "story", "milestone": False})
    steps.append({"id": "s2", "section": "section_script", "title": "反推元提示词 → 12 镜分镜表", "kind": "storyboard_meta_prompt", "milestone": False})
    steps.append({"id": "s3", "section": "section_characters", "title": "男主角", "kind": "character", "role": "male", "milestone": True})
    steps.append({"id": "s4", "section": "section_characters", "title": "女主角", "kind": "character", "role": "female", "milestone": True})
    for i, (key, label) in enumerate(SCENE_ORDER, start=5):
        steps.append({"id": f"s{i}", "section": "section_scenes", "title": label, "kind": "scene", "sceneKey": key, "milestone": True})
    for shot_n in range(1, 13):
        steps.append({"id": f"s{11+shot_n}", "section": "section_shots", "title": f"第 {shot_n} 镜", "kind": "shot", "shotNumber": shot_n, "milestone": True})
    return steps


# ---------- Sanitization ----------

NAME_MAP = [("阿木", "男主角"), ("小汐", "女主角")]
LEAK_TERMS = ("libtv", "liblib", "LibTV", "Liblib")


def scrub_text(s):
    if not isinstance(s, str) or not s:
        return s
    for a, b in NAME_MAP:
        s = s.replace(a, b)
    return s


def scrub_obj(obj):
    if isinstance(obj, str):
        t = scrub_text(obj)
        if any(term in t for term in LEAK_TERMS):
            return ""  # safety: drop any string that still leaks source name
        return t
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    return obj


# ---------- Main ----------

def main():
    raw = load_source()
    pm = raw["data"].get("projectMeta", {})
    raw_nodes = raw["data"].get("nodeList", [])
    nodes = [node_summary(n) for n in raw_nodes]
    nodes_sorted = sorted(nodes, key=lambda n: (n["positionY"], n["positionX"]))

    # ---- research-notes.md ----
    lines = ["# 25 厘米的距离 · 研究笔记（私有，不公开）", ""]
    lines.append("> 自动生成自 `source.json`，**不要**贴到学员页面。")
    lines.append("")
    lines.append(f"- 原始项目名：{pm.get('name','')}")
    sb_node = next((n for n in nodes if n["type"] == 1), None)
    storyboard_rows = []
    sb_meta_prompt = ""
    if sb_node:
        for orig in raw_nodes:
            if orig.get("nodeKey") == sb_node["nodeKey"]:
                d = parse_data(orig)
                storyboard_rows = d.get("rows") or []
                sb_meta_prompt = (d.get("params") or {}).get("prompt", "")
                break

    lines.append("")
    lines.append("## 全节点清单（按画布 Y 排序）")
    lines.append("")
    lines.append("| # | type | name | model | urls | 推断 | prompt |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, n in enumerate(nodes_sorted, 1):
        tag = "脚本" if n["type"] == 1 else ("video" if n["type"] == 3 else classify_image_role(n))
        prm = (n["prompt"] or "").replace("\n", " ").replace("|", "/")[:80]
        lines.append(f"| {i} | {n['type']} | {n['name']} | {n['model']} | {len(n['urls'])} | {tag} | {prm} |")
    lines.append("")
    lines.append("## 全 URL 清单（按节点分组）")
    lines.append("")
    for n in nodes_sorted:
        if not n["urls"]:
            continue
        lines.append(f"### [{n['type']}] {n['name']} · model={n['model']}")
        for u in n["urls"]:
            lines.append(f"- {u}")
        lines.append("")

    OUT_NOTES.write_text("\n".join(lines), encoding="utf-8")

    # ---- bucketing ----
    image_nodes = [n for n in nodes if n["type"] == 2]
    by_role = defaultdict(list)
    by_scene = defaultdict(list)
    for n in image_nodes:
        role = classify_image_role(n)
        if role.startswith("scene_final::"):
            by_scene[role.split("::", 1)[1]].append(n)
        else:
            by_role[role].append(n)
    sketch_nodes = [n for n in image_nodes if classify_image_role(n) == "scene_sketch"]

    skeleton = build_skeleton()
    course_steps = []

    def make_card(title, desc, prompt, output_urls, step_slug, role,
                  *, milestone=False, upload_key=None,
                  knowledge=None, storyboard_row=None,
                  input_assets=None, tools_node=None):
        outputs = ASSETS.assign_list(output_urls, step_slug, role) if output_urls else []
        card = {
            "title": title,
            "desc": desc,
            "prompt": prompt,
            "promptSegments": segment_prompt(prompt) if prompt else [],
            "inputAssets": input_assets or [],
            "outputAssets": outputs,
            "tools": recommend_tools(tools_node) if tools_node else [],
            "milestone": milestone,
        }
        if upload_key: card["uploadKey"] = upload_key
        if knowledge: card.update(knowledge)
        if storyboard_row: card["storyboardRow"] = storyboard_row
        return card

    for step in skeleton:
        out = {
            "id": step["id"],
            "section": step["section"],
            "title": step["title"],
            "kind": step["kind"],
            "milestone": step["milestone"],
            "subCards": [],
        }

        if step["kind"] == "story":
            out["body"] = sb_meta_prompt  # the story itself was the prompt input to the table
            # Actually the story is plainer (params.prompt). Keep it.
            # render UI shows full body + copy-all
            out["bodySegments"] = segment_prompt(sb_meta_prompt)

        elif step["kind"] == "storyboard_meta_prompt":
            meta_prompt = (
                "你是资深短片导演 + 分镜师。\n"
                "我会给你一个完整的『四幕短故事』。请基于这个故事，输出一张 12 行的分镜表，\n"
                "用 Markdown 表格回复，列依次为：\n"
                "| 镜号 | 时长(秒,3-5) | 画面描述 | 景别(特写/中景/远景/俯拍等) | 情绪 | 光影 | 音效/对白 |\n\n"
                "硬性要求：\n"
                "1. 全片共 12 镜，总时长 45~55 秒。\n"
                "2. 严格沿用故事原有的『起因-发展-高潮-结尾』四幕节奏，每幕约 3 镜。\n"
                "3. 画面描述里出现的角色只用『男主角』『女主角』指代。\n"
                "4. 景别要有变化，不要连续 3 镜都是特写。\n"
                "5. 关键情感节拍（第一次对视、靠近、表白）放在第 3/7/11 镜附近。\n"
                "6. 对白用日语并附中文翻译，如『一緒に駅まで [一起去车站吧]』。\n\n"
                "故事原文：\n<在这里粘贴第 1 步的完整故事>"
            )
            out["body"] = meta_prompt
            out["bodySegments"] = segment_prompt(meta_prompt)
            out["tools"] = [
                {"name": "Gemini", "url": "https://gemini.google.com/", "note": "推荐"},
                {"name": "ChatGPT", "url": "https://chatgpt.com/", "note": "备选"},
                {"name": "Claude", "url": "https://claude.ai/", "note": "备选"},
            ]
            out["storyboardRows"] = [
                {
                    "shotNumber": r.get("shotNumber"),
                    "durationSeconds": r.get("durationSeconds"),
                    "plotDescription": r.get("plotDescription", ""),
                    "shotSize": r.get("shotSize", ""),
                    "emotion": r.get("emotion", ""),
                    "lighting": r.get("lighting", ""),
                    "soundOrDialogue": r.get("soundOrDialogue", ""),
                }
                for r in storyboard_rows
            ]

        elif step["kind"] == "character":
            role = step["role"]
            label = "男主角" if role == "male" else "女主角"
            step_slug = f"char-{role}"
            fusion_key = "char_male_fusion" if role == "male" else "char_female_fusion"
            tv_key = "char_male_threeview" if role == "male" else "char_female_threeview"

            # 1) 参考图 card — student-supplied (upload)
            ref_card = make_card(
                f"{label} · 参考图", "挑 2~4 张能代表你想要的脸 / 气质的真人照片（自拍或公共图库）。",
                "", [], step_slug, "ref",
                upload_key=f"input_{role}_ref",
            )
            ref_card["uploadMulti"] = True
            out["subCards"].append(ref_card)

            # 2) 融合脸
            prev_outputs = []
            if by_role.get(fusion_key) or by_role.get("char_fusion"):
                n = (by_role.get(fusion_key) or by_role.get("char_fusion"))[0]
                fused = make_card(
                    f"{label} · 融合脸", "把参考图融合成一张定脸。",
                    n["prompt"], n["urls"], step_slug, "fusion",
                    input_assets=[{"placeholder": "你的参考图", "uploadKey": f"input_{role}_ref"}],
                    tools_node=n,
                )
                prev_outputs = fused["outputAssets"]
                out["subCards"].append(fused)

            # 3) 三视图
            if by_role.get(tv_key) or by_role.get("char_threeview"):
                n = (by_role.get(tv_key) or by_role.get("char_threeview"))[0]
                tv = make_card(
                    f"{label} · 三视图", "用融合脸出一张人物三视图，固定角色一致性。",
                    n["prompt"], n["urls"], step_slug, "threeview",
                    input_assets=[{"assetPath": p, "label": "融合脸"} for p in prev_outputs] or [{"placeholder": "上一步：融合脸"}],
                    tools_node=n,
                )
                prev_outputs = tv["outputAssets"]
                out["subCards"].append(tv)

            # 4) 定妆图（milestone）
            out["subCards"].append(make_card(
                f"{label} · 定妆图（milestone）",
                "从三视图里挑一张最满意的全身/半身定妆，上传保存。后续场景生成都会引用这张。",
                "", [], step_slug, "final",
                input_assets=[{"assetPath": p, "label": "三视图"} for p in prev_outputs],
                milestone=True, upload_key=f"milestone_{role}_final",
            ))

        elif step["kind"] == "scene":
            key = step["sceneKey"]
            label = step["title"]
            step_slug = f"scene-{key}"

            # 1) ref upload
            out["subCards"].append(make_card(
                f"{label} · 参考图", "挑 1~3 张参考构图（电影截图 / Pinterest / 自己拍的）。",
                "", [], step_slug, "ref",
                upload_key=f"input_scene_{key}_ref",
            ))

            # 2) 线稿
            prev_outputs = []
            if sketch_nodes:
                n = sketch_nodes[0]
                sk = make_card(
                    f"{label} · 线稿", "把参考图转线稿，保持构图。",
                    n["prompt"], n["urls"], step_slug, "sketch",
                    input_assets=[{"placeholder": "你的参考图", "uploadKey": f"input_scene_{key}_ref"}],
                    tools_node=n,
                )
                prev_outputs = sk["outputAssets"]
                out["subCards"].append(sk)

            # 3) image2image
            if by_scene.get(key):
                n = max(by_scene[key], key=lambda x: len(x["prompt"]))
                i2i = make_card(
                    f"{label} · image2image 出图",
                    "用线稿 + 男女主定妆图，生成最终场景图。",
                    n["prompt"], n["urls"], step_slug, "i2i",
                    input_assets=[
                        {"assetPath": p, "label": "线稿"} for p in prev_outputs
                    ] + [
                        {"placeholder": "男主定妆图", "uploadKey": "milestone_male_final"},
                        {"placeholder": "女主定妆图", "uploadKey": "milestone_female_final"},
                    ],
                    tools_node=n,
                )
                prev_outputs = i2i["outputAssets"]
                # add variants
                others = [m for m in by_scene[key] if m is not n]
                variant_urls = [u for m in others for u in m["urls"][:2]]
                if variant_urls:
                    i2i["variantAssets"] = ASSETS.assign_list(variant_urls, step_slug, "i2i-var")
                out["subCards"].append(i2i)

            # 4) milestone upload
            out["subCards"].append(make_card(
                f"{label} · 最终场景图（milestone）",
                "挑一张最终场景图上传保存。",
                "", [], step_slug, "final",
                input_assets=[{"assetPath": p, "label": "image2image 候选"} for p in prev_outputs],
                milestone=True, upload_key=f"milestone_scene_{key}",
            ))

        elif step["kind"] == "shot":
            shot_n = step["shotNumber"]
            step_slug = f"shot-{shot_n:02d}"
            row = next((r for r in storyboard_rows if r.get("shotNumber") == shot_n), None)
            if row:
                out["subCards"].append({
                    "title": f"第 {shot_n} 镜 · 分镜表行",
                    "desc": "本镜的核心参数。",
                    "prompt": "", "promptSegments": [],
                    "inputAssets": [], "outputAssets": [], "tools": [],
                    "storyboardRow": {
                        "shotNumber": row.get("shotNumber"),
                        "durationSeconds": row.get("durationSeconds"),
                        "plotDescription": row.get("plotDescription", ""),
                        "shotSize": row.get("shotSize", ""),
                        "emotion": row.get("emotion", ""),
                        "lighting": row.get("lighting", ""),
                        "soundOrDialogue": row.get("soundOrDialogue", ""),
                    },
                })
                img_prompt = row.get("imageGenerationPrompt") or row.get("imagePrompt") or ""
                vid_prompt = row.get("videoMotionPrompt") or row.get("videoPrompt") or ""
                if not img_prompt:
                    for k in row:
                        if "image" in k.lower() and "prompt" in k.lower():
                            img_prompt = row[k] or ""
                if not vid_prompt:
                    for k in row:
                        if "video" in k.lower() and "prompt" in k.lower():
                            vid_prompt = row[k] or ""
                kf_outputs = []
                if img_prompt:
                    kf = make_card(
                        f"第 {shot_n} 镜 · 关键帧出图",
                        "用画面描述 + 景别 + 角色定妆 + 场景图，出关键帧。",
                        img_prompt, [], step_slug, "keyframe",
                        input_assets=[
                            {"placeholder": "男主定妆图", "uploadKey": "milestone_male_final"},
                            {"placeholder": "女主定妆图", "uploadKey": "milestone_female_final"},
                        ],
                        tools_node={"type": 2, "model": "nebula-2-flash", "prompt": "三视图"},
                    )
                    kf_outputs = kf["outputAssets"]
                    out["subCards"].append(kf)
                if vid_prompt:
                    out["subCards"].append(make_card(
                        f"第 {shot_n} 镜 · 图生视频",
                        "用关键帧 + 运动描述，出 3-5 秒视频。",
                        vid_prompt, [], step_slug, "video",
                        input_assets=[{"placeholder": "上一步：关键帧", "uploadKey": f"milestone_shot_{shot_n}_keyframe"}],
                        tools_node={"type": 3, "model": "wanx2.7-video", "prompt": "", "enableSound": False},
                    ))
            else:
                out["subCards"].append({
                    "title": f"第 {shot_n} 镜",
                    "desc": "暂无分镜表对应行；先在 step 2 反推分镜表。",
                    "prompt": "", "promptSegments": [],
                    "inputAssets": [], "outputAssets": [], "tools": [],
                })

            # milestone
            out["subCards"].append(make_card(
                f"第 {shot_n} 镜 · 最终视频（milestone）",
                "把最终视频上传保存。",
                "", [], step_slug, "final",
                input_assets=[{"placeholder": "图生视频候选"}],
                milestone=True, upload_key=f"milestone_shot_{shot_n}",
            ))

            tech = SHOT_TECHNIQUES.get(shot_n)
            if tech:
                out["subCards"].append({
                    "title": "拓展知识",
                    "desc": tech["desc"],
                    "knowledgeKey": tech["key"],
                    "knowledgeTitle": tech["title"],
                    "prompt": "", "promptSegments": [],
                    "inputAssets": [], "outputAssets": [], "tools": [],
                })

        course_steps.append(out)

    case_data = {
        "meta": {
            "id": CASE_ID,
            "title": "25 厘米的距离",
            "subtitle": "四幕短故事 · 12 分镜 · 完整复刻流程",
            "version": "0.3.0",
            "updatedAt": "2026-05-23",
            "sections": SECTIONS,
        },
        "steps": course_steps,
    }

    case_data = scrub_obj(case_data)

    OUT_DATA.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(ASSETS.manifest(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {OUT_NOTES.relative_to(ROOT)}")
    print(f"wrote {OUT_DATA.relative_to(ROOT)}")
    print(f"wrote {OUT_MANIFEST.relative_to(ROOT)}  ({len(ASSETS.url_to_path)} assets to fetch)")

    fetch_assets()


def fetch_assets():
    """Download every URL in the manifest into web/assets/<case-id>/.
    Skips files that already exist. Reports failures but never aborts the build.
    Outbound to source CDN may be blocked in some environments; run this on a
    machine with normal internet access.
    """
    import urllib.request, ssl, time
    manifest = json.loads(OUT_MANIFEST.read_text(encoding="utf-8"))
    web_root = ROOT / "web"
    todo = []
    for local_path, url in manifest.items():
        dst = web_root / local_path
        if dst.exists() and dst.stat().st_size > 0:
            continue
        todo.append((local_path, url, dst))
    if not todo:
        print("[assets] all already present, nothing to download")
        return
    print(f"[assets] downloading {len(todo)} files into web/assets/...")
    ok = 0
    fail = []
    ctx = ssl.create_default_context()
    for i, (local_path, url, dst) in enumerate(todo, 1):
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.liblib.art/",
            })
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                data = r.read()
            if len(data) < 200:
                raise RuntimeError(f"suspiciously small ({len(data)} bytes)")
            dst.write_bytes(data)
            ok += 1
            print(f"  [{i}/{len(todo)}] ok  {local_path}  ({len(data)//1024} KB)")
        except Exception as e:
            fail.append((local_path, str(e)))
            print(f"  [{i}/{len(todo)}] FAIL {local_path}  {e}")
        time.sleep(0.05)
    print(f"[assets] done: {ok} ok, {len(fail)} failed")
    if fail:
        print("[assets] re-run the same command to retry failed downloads")


SHOT_TECHNIQUES = {
    1:  {"key": "establishing_shot", "title": "建置镜头",      "desc": "用一个广角远景告诉观众『发生在哪里、什么时间、什么氛围』。"},
    2:  {"key": "match_cut",         "title": "动作匹配剪辑",  "desc": "前后两镜用相似的动作/形状衔接，让转场无缝。"},
    3:  {"key": "montage",           "title": "蒙太奇",        "desc": "把多个不同时空的短镜头按情绪/主题剪到一起，压缩时间。"},
    4:  {"key": "close_up",          "title": "面部特写",      "desc": "镜头紧贴五官，把内心活动放到最大。"},
    5:  {"key": "dolly_zoom",        "title": "希区柯克变焦",   "desc": "推镜的同时反向变焦，背景被『拉离/挤压』，营造眩晕/顿悟。"},
    6:  {"key": "tracking_shot",     "title": "跟拍",          "desc": "摄影机跟着主体运动，让观众『随他/她一起前进』。"},
    7:  {"key": "shot_reverse_shot", "title": "正反打",        "desc": "两个角色对话时，A 看 B 切 B 看 A。"},
    8:  {"key": "steadicam",         "title": "斯坦尼康长镜头", "desc": "稳定器跟随的长镜头。"},
    9:  {"key": "rack_focus",        "title": "焦点切换",      "desc": "同一镜头里把焦点从前景挪到后景。"},
    10: {"key": "low_angle",         "title": "低角度仰拍",     "desc": "从下往上拍，强调主体的高度/力量。"},
    11: {"key": "snap_zoom",         "title": "急推",          "desc": "瞬间快速推镜，常用在情绪爆点。"},
    12: {"key": "long_take",         "title": "长镜头",        "desc": "一镜到底不切，把观众『困在』情绪里。"},
}


if __name__ == "__main__":
    main()
