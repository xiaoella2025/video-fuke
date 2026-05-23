# 25厘米复刻工具

视频复刻带教工具 · 第一版（v0.1.0）

一步步带你把一条参考短视频，用低成本工具链复刻出属于你自己的版本。
第一版**不调用任何 API**，所有 AI 操作都通过复制提示词，手动粘贴到豆包 / DeepSeek / Liblib / 即梦 等工具中完成。

## 本地运行

任选一种：

```bash
# Python 3
python3 -m http.server 5173
# 或 Node
npx serve .
```

然后浏览器打开 http://localhost:5173 。

> 直接双击 `index.html` 会因为浏览器禁止 `file://` 下的 `fetch` 而无法加载 `courseData.json`，请用本地服务器打开。

## 项目结构

```
index.html        # 页面壳
app.js            # 加载 courseData.json，渲染步骤、提示词、检查点
style.css         # 极简样式
courseData.json   # 课程结构化数据（流程、说明、素材、工具、提示词、检查点）
```

## 修改课程内容

只需要改 `courseData.json`，刷新页面即可。`steps[]` 里每个步骤的字段：

- `title` / `goal` — 标题、目标
- `instructions[]` — 操作步骤
- `materials[]` — 用户需要准备的素材
- `tools[]` — 引用 `tools[]` 里的 id
- `prompts[]` — `{title, body}`，body 会出现在页面上、可一键复制
- `checkpoints[]` — 勾选状态存在 localStorage，刷新不丢

## 路线图

- v0.1：纯前端 + 复制提示词（当前）
- v0.2：把生成的素材（图、片段）拖到页面上做归档
- v0.3：可选接入 API（豆包 / DeepSeek）做提示词自动调用
