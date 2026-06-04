# 视频复刻案例数据清洗 Skill

## 一、Skill 用途

这个 Skill 用于把新案例的原始画布数据整理成学员能看懂、能复刻操作的 `courseData.json`。

目标包括：

1. 学员端不显示后台模型字段。
2. 输入图 / 输入视频尽量补齐。
3. 场景链路能从图走到视频。
4. 分镜页不能只有文字，要能看到对应出图和出视频链路。
5. 视频延长 / 补帧不能孤立展示。
6. 每次优先只改目标 case 的 `courseData.json`。

## 二、固定边界

正常清洗时，优先只修改：

`course-data/case-xx/courseData.json`

不要随便修改：

1. `course-data/25cm/courseData.json`
2. `web/`
3. `scripts/`
4. `source.json`
5. `asset-manifest.json`
6. `video-reference-audit.json`
7. `video-reference-audit.md`
8. 图片资源
9. 视频资源

## 三、模型字段清洗规则

禁止学员端出现后台字段，例如：

1. `mj-v7`
2. `nebula-ultra`
3. `kling-video-o3`
4. `kling-v3-omni`
5. `scene-2`
6. `viduq2-pro`
7. `viduq3-pro`
8. 原平台模型
9. 原节点模型
10. 本节点
11. 本案例使用模型
12. 内部模型 ID
13. 按原节点模型复刻
14. 待确认
15. `{}`
16. `推荐参数 {}`

清洗原则：

1. 公开模型可以显示，例如 Midjourney V7、Kling O3、Kling 3.0。
2. 内部模型不要显示。
3. 角色一致性可以推荐：Nano Banana / 即梦 / Midjourney V7。
4. 场景图、分镜图可以推荐：即梦 / Midjourney V7 / Nano Banana。
5. 视频生成可以推荐：Kling 3.0 / Kling O3 / 即梦 AI / Runway / Veo。

不要出现：

1. `LibTV`
2. `LibLib`
3. `Lib Navo`
4. `Lib Navo Pro`

## 四、输入图缺失补全规则

如果提示词里出现以下内容，但页面显示“无输入”，需要反查输入图：

1. `Image`
2. `Portrait`
3. `Mixed`
4. 图1
5. 图2
6. 图3
7. 图片1
8. 图片2
9. 参考图
10. 三视图
11. 根据参考图片

反查顺序：

1. 当前节点的 `params.imageList`
2. 当前节点的 `inputUrls`
3. manifest 里的 `inputUrls`
4. `classification / upstream` 信息
5. `source.json` 里的 incoming connections
6. 同 `outputUrl` 的兄弟节点
7. 同 prompt 或高相似 prompt 的变体节点
8. 同批次多结果节点

注意：

1. 不要把结果图误当输入图。
2. 不要把视频 URL 塞进 `inputs.images`。
3. 不要乱拿相邻图片。
4. 不要为了页面显示破坏数据结构。

## 五、场景链路补回规则

场景准备里不能只显示图片。

如果原始数据中有对应视频，应该尽量整理成：

```text
参考图 / 场景图
→ 图片提示词
→ 图片结果
→ 视频提示词
→ 输出视频
```

如果 `source.json` 里有视频，但 `courseData.json` 没有展示，要检查视频是否没有挂回对应场景链路。

## 六、分镜链路绑定规则

分镜准备不能只有分镜文字。

每个分镜段应尽量包含：

```text
分镜说明
→ 出图链路
→ 出视频链路
```

学员应该能看到：

1. 第几段
2. 时长
3. 画面描述
4. 景别
5. 情绪
6. 光影
7. 图片提示词
8. 视频提示词
9. 输出视频

## 七、视频延长 / 补帧规则

视频延长不能孤立展示成：

```text
无输入 → 延长提示词 → 输出视频
```

必须整理成：

```text
原视频 / 上游视频
→ 延长提示词
→ 延长后视频
```

如果课程里有“视频延长与补帧”专题段，可以保留专题段。

但对应原分镜段里也应该展示延长动作。

推荐结构：

位置 1：原分镜段

```text
原视频 → 延长提示词 → 延长后视频
```

位置 2：专题段

```text
原视频 → 延长提示词 → 延长后视频
```

注意：

1. 不要删除原视频。
2. 不要删除延长后视频。
3. 不要把延长视频做成孤立 chain。
4. 不要把视频 URL 塞进 `inputs.images`。
5. 输入视频应该放在 `inputs.videos`。

## 八、每次清洗后的自检清单

每次完成 case 清洗后，必须自检：

1. JSON 能正常解析。
2. `git diff --name-only` 只包含允许修改的文件。
3. 禁用词扫描无命中。
4. `inputs.images` 中没有视频 URL。
5. 输出视频没有被误填成输入视频。
6. 场景准备中能挂视频的链路已挂回。
7. 分镜准备不是只有文字。
8. 延长视频不是孤立链路。
9. 原视频和延长后视频都保留。
10. 没有改 `25cm`。
11. 没有改 `web`。
12. 没有改 `source.json`。
13. 没有改 manifest / audit 文件。
14. 没有改图片 / 视频资源。
15. `reason / note` 中没有技术残留，例如 `source.json`、节点、清洗、内部字段、待确认。

## 九、输出报告格式

以后每次执行清洗任务后，按这个格式输出报告：

1. 修改文件列表
2. 是否只修改了目标 case 的 `courseData.json`
3. 模型字段清洗结果
4. 输入图补全结果
5. 场景视频链路补回结果
6. 分镜链路绑定结果
7. 视频延长 / 补帧整理结果
8. 禁用词扫描结果
9. JSON 解析结果
10. git diff 摘要
11. 自检清单

## 十、提交要求

沉淀 Skill 文档时，只提交文档本身。

推荐提交命令：

```bash
git add docs/video-fuke-case-cleanup-skill.md
git commit -m "docs: add video fuke case cleanup skill"
```

不要修改其他文件，不做脚本，不改页面，不改数据。
