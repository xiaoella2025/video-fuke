#!/usr/bin/env python3
"""
build-course-data.py

Reads course-data/25cm/source.json (raw LibTV canvas export, lightly malformed),
emits:
  - course-data/25cm/research-notes.md  (full inventory; private, do NOT publish)
  - course-data/25cm/courseData.json    (sanitized course data for the web app)

The sanitized output never references LibTV, the original author, the source
platform, or any internal model name. External-tool recommendations follow the
mapping table in the project handoff.
"""
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "course-data" / "25cm" / "source.json"
OUT_NOTES = ROOT / "course-data" / "25cm" / "research-notes.md"
OUT_DATA = ROOT / "course-data" / "25cm" / "courseData.json"


# ---------- JSON repair ----------

def repair_json_text(raw: str) -> str:
    # 0. missing opening quote on bare keys, e.g.  `  nodeKey": ...`
    raw = re.sub(r'(\n\s+)([A-Za-z_][A-Za-z0-9_]*)(":)', r'\1"\2\3', raw)

    # 1. missing comma when a value-ending line is followed by a "key": line
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

    # 2. leading-zero redactions: ": 007" → ": 0"
    raw = re.sub(r'(:\s*)0+(\d+)(?=\s*[,\n}\]])', r'\g<1>0', raw)
    return raw


def load_source():
    text = SRC.read_text(encoding="utf-8")
    text = repair_json_text(text)
    return json.loads(text)


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


# ---------- External tool recommendation ----------

def recommend_tools(node):
    """Map internal model → external tool list. Pure mapping; never leaks internal name."""
    m = node["model"]
    p = node["prompt"]
    if m == "aurora-3-prime" or node["type"] == 1:
        return [
            {"name": "Gemini", "url": "https://gemini.google.com/", "note": "推荐：长文/分镜表反推强"},
            {"name": "ChatGPT", "url": "https://chatgpt.com/", "note": "备选"},
            {"name": "Claude", "url": "https://claude.ai/", "note": "备选"},
        ]
    if node["type"] == 3:
        if node["enableSound"]:
            return [
                {"name": "Google Veo", "url": "https://deepmind.google/technologies/veo/", "note": "推荐：原生带声，可日语对白"},
                {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选：先无声出片，再配音"},
            ]
        return [
            {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "推荐：图生视频"},
            {"name": "Runway", "url": "https://runwayml.com/", "note": "备选"},
        ]
    # image
    if "三视图" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/", "note": "推荐：角色一致性强"},
            {"name": "Midjourney", "url": "https://www.midjourney.com/", "note": "备选"},
        ]
    if "Integrate features" in p or "融合" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/", "note": "推荐：人脸融合稳定"},
            {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选"},
        ]
    if "线稿" in p or "草图" in p or "Sketch" in p:
        return [
            {"name": "Nano Banana", "url": "https://nanobanana.ai/", "note": "推荐：i2i 线稿"},
            {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选"},
        ]
    return [
        {"name": "Midjourney", "url": "https://www.midjourney.com/", "note": "推荐：电影感场景图"},
        {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选"},
    ]


# ---------- Prompt segmentation (auto-fold blocks) ----------

def segment_prompt(text: str):
    """Split a long prompt into labeled blocks for the UI to render as foldable sections.
    Output: [{label, body}]. Keep it simple — split on blank lines / numbered sections.
    """
    if not text or not text.strip():
        return []
    # Split on blank lines OR Chinese section markers like 第X幕/第X部分
    parts = re.split(r"\n\s*\n", text.strip())
    segs = []
    for i, part in enumerate(parts, 1):
        part = part.strip()
        if not part:
            continue
        # try to grab a label from first 24 chars
        first_line = part.splitlines()[0]
        if len(part) <= 80:
            label = f"段 {i}"
        else:
            head = first_line[:24]
            label = f"段 {i}：{head}…" if len(first_line) > 24 else f"段 {i}：{first_line}"
        segs.append({"label": label, "body": part})
    return segs


# ---------- Scene/character classification (heuristic) ----------

SCENE_RULES = [
    ("stairs_first_meet",   "楼梯初遇",    ["阶梯", "汽水", "鞋柜", "玄关", "系鞋带"]),
    ("classroom_glance",    "教室偷看",    ["图书馆", "教室", "肩并肩", "偷偷看对方", "桌子上"]),
    ("grass_earphones",     "草地耳机",    ["草地", "耳机", "躺在草地", "耳朵"]),
    ("eye_contact",         "对视特写",    ["互相看着", "特写", "对视"]),
    ("seaside_bike",        "海边骑行",    ["自行车", "骑着", "海边", "骑行", "迎着海风"]),
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
    p = node["prompt"]
    name = node["name"]
    # character builds
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
    # scene final image
    scene_key, _ = classify_scene(p + " " + name)
    if scene_key:
        return f"scene_final::{scene_key}"
    return "other"


# ---------- Step skeleton (23 steps) ----------

SCENE_ORDER = [
    ("stairs_first_meet",   "楼梯初遇"),
    ("classroom_glance",    "教室偷看"),
    ("grass_earphones",     "草地共听耳机"),
    ("eye_contact",         "对视特写"),
    ("seaside_bike",        "海边骑行"),
    ("stone_skip_fuji",     "打水漂富士山"),
    ("fireworks_festival",  "烟花祭"),
]


def build_skeleton(rows_in_storyboard):
    """Return the 23-step skeleton with titles & section labels."""
    steps = []

    # Segment 1: script prep (2)
    steps.append({"id": "s1", "section": "段1 脚本准备", "title": "完整故事（四幕原文）",
                  "kind": "story", "milestone": False})
    steps.append({"id": "s2", "section": "段1 脚本准备", "title": "反推元提示词 → 12 镜分镜表",
                  "kind": "storyboard_meta_prompt", "milestone": False})

    # Segment 2: characters (2)
    steps.append({"id": "s3", "section": "段2 角色准备", "title": "男主角",
                  "kind": "character", "role": "male", "milestone": True})
    steps.append({"id": "s4", "section": "段2 角色准备", "title": "女主角",
                  "kind": "character", "role": "female", "milestone": True})

    # Segment 3: scenes (7)
    for i, (key, label) in enumerate(SCENE_ORDER, start=5):
        steps.append({"id": f"s{i}", "section": "段3 场景准备", "title": label,
                      "kind": "scene", "sceneKey": key, "milestone": True})

    # Segment 4: 12 shots
    for shot_n in range(1, 13):
        steps.append({"id": f"s{11 + shot_n}", "section": "段4 12 分镜",
                      "title": f"第 {shot_n} 镜", "kind": "shot", "shotNumber": shot_n,
                      "milestone": True})

    return steps


# ---------- Main ----------

def main():
    raw = load_source()
    pm = raw["data"].get("projectMeta", {})
    nodes = [node_summary(n) for n in raw["data"].get("nodeList", [])]
    nodes_sorted = sorted(nodes, key=lambda n: (n["positionY"], n["positionX"]))

    # ---- research-notes.md (full inventory; private) ----
    lines = []
    lines.append("# 25 厘米的距离 · 研究笔记（私有，不公开）")
    lines.append("")
    lines.append("> 自动生成自 `source.json`。仅供研究/开发使用，**不要**把内容贴入面向学员的页面。")
    lines.append("")
    lines.append(f"- 原始项目名：{pm.get('name','')}")
    lines.append(f"- 节点总数：{len(nodes)}（type=1 脚本×{sum(1 for n in nodes if n['type']==1)} / type=2 图像×{sum(1 for n in nodes if n['type']==2)} / type=3 视频×{sum(1 for n in nodes if n['type']==3)}）")
    lines.append("")

    # type 1 (storyboard table)
    lines.append("## 1. 脚本节点（type=1）")
    sb_node = next((n for n in nodes if n["type"] == 1), None)
    storyboard_rows = []
    if sb_node:
        # locate the original parsed node to grab rows
        for orig in raw["data"]["nodeList"]:
            if orig.get("nodeKey") == sb_node["nodeKey"]:
                d = parse_data(orig)
                storyboard_rows = d.get("rows") or []
                lines.append(f"- 标题：{d.get('title','')}")
                lines.append(f"- 模型：{(d.get('params') or {}).get('model','')}")
                lines.append(f"- 行数：{len(storyboard_rows)}")
                lines.append("")
                lines.append("### 元提示词 prompt（原文）")
                lines.append("")
                lines.append("```")
                lines.append((d.get("params") or {}).get("prompt", ""))
                lines.append("```")
                break

    # full inventory
    lines.append("")
    lines.append("## 2. 全节点清单（按画布 Y 排序）")
    lines.append("")
    lines.append("| # | type | name | model | urls | scene/role 推断 | prompt(摘要) |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, n in enumerate(nodes_sorted, 1):
        if n["type"] == 1:
            tag = "脚本"
        elif n["type"] == 3:
            tag = "video"
        else:
            tag = classify_image_role(n)
        prm = (n["prompt"] or "").replace("\n", " ").replace("|", "/")[:80]
        lines.append(f"| {i} | {n['type']} | {n['name']} | {n['model']} | {len(n['urls'])} | {tag} | {prm} |")
    lines.append("")

    # full URL dump (so we can manually pick stills)
    lines.append("## 3. 全 URL 清单")
    lines.append("")
    for n in nodes_sorted:
        if not n["urls"]:
            continue
        lines.append(f"### [{n['type']}] {n['name']} · model={n['model']}")
        for u in n["urls"]:
            lines.append(f"- {u}")
        lines.append("")

    OUT_NOTES.write_text("\n".join(lines), encoding="utf-8")

    # ---- courseData.json (sanitized) ----
    image_nodes = [n for n in nodes if n["type"] == 2]
    video_nodes = [n for n in nodes if n["type"] == 3]

    # bucketing
    by_role = defaultdict(list)
    by_scene = defaultdict(list)
    for n in image_nodes:
        role = classify_image_role(n)
        if role.startswith("scene_final::"):
            by_scene[role.split("::", 1)[1]].append(n)
        else:
            by_role[role].append(n)

    by_scene_sketch = [n for n in image_nodes if classify_image_role(n) == "scene_sketch"]

    # video by scene
    video_by_scene = defaultdict(list)
    for v in video_nodes:
        k, _ = classify_scene(v["prompt"])
        if k:
            video_by_scene[k].append(v)

    def serialize_node(n):
        return {
            "name": n["name"],
            "prompt": n["prompt"],
            "promptSegments": segment_prompt(n["prompt"]),
            "previewImages": n["urls"][:4],
            "tools": recommend_tools(n),
            "sound": bool(n.get("enableSound")),
        }

    skeleton = build_skeleton(storyboard_rows)
    course_steps = []
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
            # show 4-act story body. We don't store author name etc.
            story = ""
            params_text = ""
            if sb_node:
                for orig in raw["data"]["nodeList"]:
                    if orig.get("nodeKey") == sb_node["nodeKey"]:
                        params_text = (parse_data(orig).get("params") or {}).get("prompt", "")
                        break
            out["body"] = params_text
            out["bodySegments"] = segment_prompt(params_text)

        elif step["kind"] == "storyboard_meta_prompt":
            # reverse-engineered meta-prompt (hand-authored; not from source)
            meta_prompt = (
                "你是资深短片导演 + 分镜师。\n"
                "我会给你一个完整的『四幕短故事』。请基于这个故事，输出一张 12 行的分镜表，\n"
                "用 Markdown 表格回复，列依次为：\n"
                "| 镜号 | 时长(秒,3-5) | 画面描述 | 景别(特写/中景/远景/俯拍等) | 情绪 | 光影 | 音效/对白 |\n\n"
                "硬性要求：\n"
                "1. 全片共 12 镜，总时长 45~55 秒。\n"
                "2. 严格沿用故事原有的『起因-发展-高潮-结尾』四幕节奏，每幕约 3 镜。\n"
                "3. 画面描述里出现的角色，只用『男主角』『女主角』指代，不要给名字。\n"
                "4. 景别要有变化（不要连续 3 镜都是特写），整体节奏前慢后快。\n"
                "5. 关键的情感节拍（第一次对视、第一次靠近、表白瞬间）放在第 3/7/11 镜附近。\n"
                "6. 对白必须是日语，并在中括号里附中文翻译，如『一緒に駅まで [一起去车站吧]』。\n\n"
                "故事原文：\n"
                "<在这里粘贴第 1 步的完整故事>"
            )
            out["body"] = meta_prompt
            out["bodySegments"] = segment_prompt(meta_prompt)
            out["tools"] = [
                {"name": "Gemini", "url": "https://gemini.google.com/", "note": "推荐"},
                {"name": "ChatGPT", "url": "https://chatgpt.com/", "note": "备选"},
                {"name": "Claude", "url": "https://claude.ai/", "note": "备选"},
            ]
            # Also expose the actual storyboard rows for reference
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
            fusion_key = "char_male_fusion" if role == "male" else "char_female_fusion"
            threeview_key = "char_male_threeview" if role == "male" else "char_female_threeview"
            label = "男主角" if role == "male" else "女主角"
            sub = []
            sub.append({
                "title": f"{label} · 参考图",
                "desc": "从外部素材里挑 2~4 张能代表你想要的脸 / 气质的真人照片作为参考（自己照片、公共图库均可）。",
                "tools": [],
                "prompt": "",
                "previewImages": [],
            })
            # 融合脸
            if by_role.get(fusion_key) or by_role.get("char_fusion"):
                ref = (by_role.get(fusion_key) or by_role.get("char_fusion"))[0]
                sub.append({
                    "title": f"{label} · 融合脸",
                    "desc": "把参考图融合成一张定脸。",
                    "tools": ref["tools"] if isinstance(ref, dict) and "tools" in ref else recommend_tools(ref),
                    "prompt": ref["prompt"],
                    "promptSegments": segment_prompt(ref["prompt"]),
                    "previewImages": ref["urls"][:4],
                })
            # 三视图
            if by_role.get(threeview_key) or by_role.get("char_threeview"):
                ref = (by_role.get(threeview_key) or by_role.get("char_threeview"))[0]
                sub.append({
                    "title": f"{label} · 三视图",
                    "desc": "用融合脸出一张人物三视图，固定角色一致性。",
                    "tools": recommend_tools(ref),
                    "prompt": ref["prompt"],
                    "promptSegments": segment_prompt(ref["prompt"]),
                    "previewImages": ref["urls"][:4],
                })
            sub.append({
                "title": f"{label} · 定妆图（milestone）",
                "desc": "挑一张你最满意的全身/半身定妆，上传保存。后续所有场景生成都会引用这张。",
                "tools": [],
                "prompt": "",
                "previewImages": [],
                "milestone": True,
                "uploadKey": f"milestone_{role}_final",
            })
            out["subCards"] = sub

        elif step["kind"] == "scene":
            key = step["sceneKey"]
            label = step["title"]
            sub = []
            sub.append({
                "title": f"{label} · 参考图",
                "desc": "从电影截图 / Pinterest / 自己拍的照片里挑 1~3 张参考构图。",
                "tools": [],
                "prompt": "",
                "previewImages": [],
            })
            # sketch nodes shared across scenes; pull one
            if by_scene_sketch:
                sk = by_scene_sketch[0]
                sub.append({
                    "title": f"{label} · 线稿",
                    "desc": "把参考图转成线稿，方便后续 image-to-image 时保持构图。",
                    "tools": recommend_tools(sk),
                    "prompt": sk["prompt"],
                    "promptSegments": segment_prompt(sk["prompt"]),
                    "previewImages": sk["urls"][:3],
                })
            if by_scene.get(key):
                # take the most prompt-rich one
                best = max(by_scene[key], key=lambda x: len(x["prompt"]))
                sub.append({
                    "title": f"{label} · image2image 出图",
                    "desc": "用线稿 + 男女主定妆图，生成最终场景图。",
                    "tools": recommend_tools(best),
                    "prompt": best["prompt"],
                    "promptSegments": segment_prompt(best["prompt"]),
                    "previewImages": best["urls"][:4],
                })
                # show extra variants if any
                others = [n for n in by_scene[key] if n is not best]
                if others:
                    sub[-1]["variantPreviews"] = [u for n in others for u in n["urls"][:2]]
            sub.append({
                "title": f"{label} · 最终场景图（milestone）",
                "desc": "挑一张最终场景图上传保存，后续分镜会引用。",
                "tools": [],
                "prompt": "",
                "previewImages": [],
                "milestone": True,
                "uploadKey": f"milestone_scene_{key}",
            })
            out["subCards"] = sub

        elif step["kind"] == "shot":
            shot_n = step["shotNumber"]
            row = next((r for r in storyboard_rows if r.get("shotNumber") == shot_n), None)
            sub = []
            if row:
                sub.append({
                    "title": f"第 {shot_n} 镜 · 分镜表行",
                    "desc": "本镜的画面/景别/情绪/光影/音效信息。",
                    "tools": [],
                    "prompt": "",
                    "previewImages": [],
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
                # also try fallback fields
                if not img_prompt:
                    for k in row:
                        if "image" in k.lower() and "prompt" in k.lower():
                            img_prompt = row[k] or ""
                if not vid_prompt:
                    for k in row:
                        if "video" in k.lower() and "prompt" in k.lower():
                            vid_prompt = row[k] or ""
                if img_prompt:
                    sub.append({
                        "title": f"第 {shot_n} 镜 · 关键帧出图",
                        "desc": "用本镜的画面描述和景别，结合男女主定妆 + 对应场景图出关键帧。",
                        "tools": [
                            {"name": "Nano Banana", "url": "https://nanobanana.ai/", "note": "推荐：角色一致"},
                            {"name": "Midjourney", "url": "https://www.midjourney.com/", "note": "备选"},
                        ],
                        "prompt": img_prompt,
                        "promptSegments": segment_prompt(img_prompt),
                        "previewImages": [],
                    })
                if vid_prompt:
                    sub.append({
                        "title": f"第 {shot_n} 镜 · 图生视频",
                        "desc": "用关键帧 + 运动描述，出一段 3-5 秒的视频。",
                        "tools": [
                            {"name": "Google Veo", "url": "https://deepmind.google/technologies/veo/", "note": "推荐：可带日语对白"},
                            {"name": "即梦 AI", "url": "https://jimeng.jianying.com/", "note": "备选：先无声出片"},
                        ],
                        "prompt": vid_prompt,
                        "promptSegments": segment_prompt(vid_prompt),
                        "previewImages": [],
                    })
            else:
                sub.append({
                    "title": f"第 {shot_n} 镜",
                    "desc": "（分镜表无对应行；先回到 step 2 反推分镜表）",
                    "tools": [],
                    "prompt": "",
                    "previewImages": [],
                })
            sub.append({
                "title": f"第 {shot_n} 镜 · 最终视频（milestone）",
                "desc": "把最终视频上传保存。",
                "tools": [],
                "prompt": "",
                "previewImages": [],
                "milestone": True,
                "uploadKey": f"milestone_shot_{shot_n}",
            })
            # 导演手法小卡（拓展知识）
            tech = SHOT_TECHNIQUES.get(shot_n)
            if tech:
                sub.append({
                    "title": "拓展知识",
                    "desc": tech["desc"],
                    "knowledgeKey": tech["key"],
                    "knowledgeTitle": tech["title"],
                    "tools": [],
                    "prompt": "",
                    "previewImages": [],
                })
            out["subCards"] = sub

        course_steps.append(out)

    case_data = {
        "meta": {
            "id": "25cm",
            "title": "25 厘米的距离",
            "subtitle": "四幕短故事 · 12 分镜 · 完整复刻流程",
            "version": "0.2.0",
            "updatedAt": "2026-05-23",
        },
        "steps": course_steps,
    }

    case_data = scrub_obj(case_data)
    OUT_DATA.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_NOTES.relative_to(ROOT)} ({OUT_NOTES.stat().st_size} bytes)")
    print(f"wrote {OUT_DATA.relative_to(ROOT)} ({OUT_DATA.stat().st_size} bytes)")


# ---------- Sanitization (strip source-identifying info from public output) ----------

NAME_MAP = [
    ("阿木", "男主角"),
    ("小汐", "女主角"),
]
DROP_DOMAINS = ("libtv-res.", "libtv.", "liblib")


def scrub_text(s):
    if not isinstance(s, str) or not s:
        return s
    for a, b in NAME_MAP:
        s = s.replace(a, b)
    return s


def scrub_obj(obj):
    if isinstance(obj, str):
        return scrub_text(obj)
    if isinstance(obj, list):
        out = []
        for v in obj:
            if isinstance(v, str) and any(d in v for d in DROP_DOMAINS):
                continue  # drop source-CDN URLs from public output
            out.append(scrub_obj(v))
        return out
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    return obj


# ---------- Director technique pairings (for shots 1..12) ----------

SHOT_TECHNIQUES = {
    1:  {"key": "establishing_shot", "title": "建置镜头",      "desc": "用一个广角远景告诉观众『发生在哪里、什么时间、什么氛围』。"},
    2:  {"key": "match_cut",         "title": "动作匹配剪辑",  "desc": "前后两镜用相似的动作/形状衔接，让转场无缝。"},
    3:  {"key": "montage",           "title": "蒙太奇",        "desc": "把多个不同时空的短镜头按情绪/主题剪到一起，压缩时间。"},
    4:  {"key": "close_up",          "title": "面部特写",      "desc": "镜头紧贴五官，把内心活动放到最大。"},
    5:  {"key": "dolly_zoom",        "title": "希区柯克变焦",   "desc": "推镜的同时反向变焦，背景被『拉离/挤压』，营造眩晕/顿悟。"},
    6:  {"key": "tracking_shot",     "title": "跟拍",          "desc": "摄影机跟着主体运动，让观众『随他/她一起前进』。"},
    7:  {"key": "shot_reverse_shot", "title": "正反打",        "desc": "两个角色对话时，A 看 B 切 B 看 A，最经典的对视语法。"},
    8:  {"key": "steadicam",         "title": "斯坦尼康长镜头", "desc": "稳定器跟随的长镜头，让动作流畅但不抽离。"},
    9:  {"key": "rack_focus",        "title": "焦点切换",      "desc": "同一镜头里把焦点从前景挪到后景（或反向），暗示注意力转移。"},
    10: {"key": "low_angle",         "title": "低角度仰拍",     "desc": "从下往上拍，强调主体的高度/力量/憧憬感。"},
    11: {"key": "snap_zoom",         "title": "急推",          "desc": "瞬间快速推镜，常用在情绪爆点。"},
    12: {"key": "long_take",         "title": "长镜头",        "desc": "一镜到底不切，把观众『困在』情绪里更久。"},
}


if __name__ == "__main__":
    main()
