# 视频复刻教学工具

纯静态本地 HTML 教学工具，付费学员用。一步步带你把一条短片完整复刻出来。

## 本地运行

从**项目根目录**起服务（不是 `web/` 里面），这样课程数据文件能被读到：

```bash
# Python 3
python3 -m http.server 5173
# 或 Node
npx serve .
```

打开 <http://localhost:5173/web/>。注意：直接双击 `index.html` 因为 `fetch()` 限制无法工作，必须用本地服务器。

## 目录结构

```
video-fuke/
├─ web/                          # 纯静态前端
│   ├─ index.html
│   ├─ wiki.html                 # 导演手法百科
│   ├─ app.js
│   ├─ styles.css
│   ├─ courses.json              # 案例列表（下拉框数据源）
│   └─ knowledge.json            # 导演手法百科条目
├─ course-data/
│   └─ 25cm/
│       ├─ source.json           # 原始抓回来的画布 JSON（本地分析用，不公开）
│       ├─ courseData.json       # 喂网页用的脱敏版（零来源信息）
│       └─ research-notes.md     # 给自己看的研究表（私有，不公开）
└─ scripts/
    └─ build-course-data.py      # source.json → courseData.json + research-notes.md
```

## 数据流

1. 把抓回来的画布 JSON 放到 `course-data/<case-id>/source.json`
2. 运行 `python3 scripts/build-course-data.py`
3. 自动生成 `courseData.json`（脱敏版）+ `research-notes.md`（私有研究表）
4. 在 `web/courses.json` 里加一条新案例

## 课程结构

每个案例固定 23 步：

- **段 1 脚本准备** (2 步)：完整故事、反推元提示词
- **段 2 角色准备** (2 步)：男主角、女主角（各自展开：参考图 → 融合脸 → 三视图 → 定妆图 ★）
- **段 3 场景准备** (7 步)：每个场景一步（参考图 → 线稿 → image2image → 最终场景图 ★）
- **段 4 12 分镜** (12 步)：每镜（分镜表行 → 出关键帧 → 图生视频 → 最终视频 ★）+ 拓展知识

★ = milestone 上传位（学员产物存 IndexedDB，仅本地）。

## 隐私与脱敏

- `courseData.json` **不含**任何外部来源信息（原作者 / 平台 / 角色名 / CDN URL）
- 所有源信息只保留在 `source.json` 与 `research-notes.md`（不公开、不部署）
- 学员产物只存 localStorage + IndexedDB，换浏览器即丢失，不做云端
