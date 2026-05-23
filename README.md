# 视频复刻教学工具

纯静态本地教学网页，付费学员用。一步步把一条短片完整复刻出来。

## 你只需要做一件事

```bash
python3 scripts/build-course-data.py
```

这条命令会：
1. 把 `course-data/<case>/source.json` 解析、脱敏，生成 `courseData.json`
2. 把所有需要的图片自动从远端拉到 `web/assets/<case>/` （按脱敏文件名存）
3. 同时生成你自己看的研究表 `research-notes.md`

跑完之后，开一个本地服务器：

```bash
python3 -m http.server 5173
```

打开 <http://127.0.0.1:5173/web/> 就能用了。

> 直接双击 `index.html` 因为 `fetch()` 限制不能用，必须用本地服务器。
>
> 网络受限的环境（比如代理沙箱）可能下不到图，会跳过；这时网页上对应位置会显示"图片待生成"占位框，本地再跑一次 build 就能补上。

## 课程结构（每个案例 23 步）

- **段 1 脚本准备**（2 步）：四幕原文 / 反推元提示词
- **段 2 角色准备**（2 步）：男主角 / 女主角 — 每角色内部 4 张子卡片
- **段 3 场景准备**（7 步）：楼梯初遇 / 教室偷看 / 草地共听耳机 / 对视特写 / 海边骑行 / 打水漂富士山 / 烟花祭
- **段 4 12 分镜**（12 步）：每镜 = 分镜表行 → 关键帧出图 → 图生视频 → 最终视频 + 拓展知识小卡

每个子卡片三栏：**起始图 ｜ 提示词 ｜ 结果图**。学员产物（milestone 上传）只存浏览器本地（localStorage + IndexedDB）。

## 目录结构

```
video-fuke/
├─ README.md
├─ web/                          # 纯静态前端
│   ├─ index.html · wiki.html
│   ├─ app.js · styles.css
│   ├─ courses.json              # 案例下拉数据源
│   ├─ knowledge.json            # 导演手法百科条目
│   └─ assets/<case>/            # 自动下载的图片产物
├─ course-data/<case>/
│   ├─ source.json               # 原始画布 JSON（私有）
│   ├─ courseData.json           # 喂网页用的脱敏版
│   ├─ asset-manifest.json       # 脱敏文件名 → 原 URL（私有）
│   └─ research-notes.md         # 私有研究表
└─ scripts/build-course-data.py  # 一条命令搞定上面所有事
```

## 脱敏

- `courseData.json` 不含任何外部来源信息（原作者 / 平台 / CDN URL / 内部模型名 / 角色名）
- 角色统一叫"男主角""女主角"
- 原始 URL 只保留在 `course-data/<case>/asset-manifest.json` + `research-notes.md`（私有）
