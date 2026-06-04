# 视频复刻课程一键复用指南

## 一、这份指南是做什么的

这份指南用于以后复用完整的视频复刻课程制作流程。

它不是单独的开发日志，而是以后做 `case-03`、`case-04`、`case-05` 时可以照着走的标准流程。

完整流程分成两大阶段：

1. 先整理复刻案例数据。
2. 再生成学员包、配置激活码、准备最终交付。

对应仓库里已经沉淀了两个 Skill：

- `docs/video-fuke-case-cleanup-skill.md`
- `docs/video-fuke-student-package-activation-skill.md`

这两个 Skill 不要混在一起使用。

## 二、两个 Skill 的分工

### Skill 1：视频复刻案例整理 Skill

文档路径：

```text
docs/video-fuke-case-cleanup-skill.md
```

它负责处理案例数据。

主要任务包括：

1. 整理 `source.json` / `courseData.json`
2. 清理后台模型字段
3. 补输入图
4. 补输入视频
5. 整理场景链路
6. 整理分镜链路
7. 整理视频延长 / 补帧链路
8. 输出数据自检报告

这个 Skill 只应优先修改目标案例的：

```text
course-data/case-xx/courseData.json
```

不要用它来做学员包、激活码、打包交付。

### Skill 2：视频复刻学员包与激活码 Skill

文档路径：

```text
docs/video-fuke-student-package-activation-skill.md
```

它负责处理学员交付。

主要任务包括：

1. 生成单案例学员包
2. 检查 `start.bat`
3. 设置独立端口
4. 配置最终视频入口
5. 配置机器码 / 激活码流程
6. 检查老师端激活码生成工具
7. 检查 README
8. 最终打包前自检

这个 Skill 不负责整理 `courseData.json`，也不应该修改案例数据内容。

## 三、完整复用流程

以后做一个新案例，例如 `case-03`，建议按下面顺序执行。

## 第 1 步：准备新案例原始文件

在仓库里新建：

```text
course-data/case-03/
```

把原始文件放进去。

常见文件包括：

1. 原始画布数据：

```text
course-data/case-03/source.json
```

2. 初版课程数据：

```text
course-data/case-03/courseData.json
```

如果还没有 `courseData.json`，需要先让 Codex 根据 `source.json` 生成初版。

3. 资源清单：

```text
course-data/case-03/asset-manifest.json
```

4. 视频审计文件：

```text
course-data/case-03/video-reference-audit.json
course-data/case-03/video-reference-audit.md
```

5. 图片和视频资源：

按照 `source.json` 或 manifest 里的路径放好。

如果文件还没准备齐，不要让 Codex 编造数据。应先让它告诉用户缺什么、放哪里。

## 第 2 步：启用 Skill 1，整理复刻案例数据

常用启用词：

```text
复刻新视频 case-03
```

或者：

```text
复刻这个视频 case-03
```

Codex 应该读取：

```text
docs/video-fuke-case-cleanup-skill.md
```

然后按 Skill 1 整理目标案例。

重点检查：

1. 模型字段是否有后台字段
2. 输入图是否缺失
3. 输入视频是否缺失
4. 场景链路是否从图走到视频
5. 分镜页是否只有文字
6. 视频延长 / 补帧是否孤立
7. 是否误改了 `25cm`
8. 是否误改了 `web`
9. 是否误改了 `source` / manifest / audit 文件

Skill 1 完成后，应输出报告。

报告至少包括：

1. 修改文件列表
2. 是否只修改了目标 case 的 `courseData.json`
3. 模型字段整理结果
4. 输入图补全结果
5. 输入视频补全结果
6. 场景视频链路补回结果
7. 分镜链路绑定结果
8. 视频延长 / 补帧整理结果
9. 禁用词扫描结果
10. JSON 解析结果
11. git diff 摘要
12. 自检清单

## 第 3 步：本地验收案例数据

Skill 1 完成后，先不要急着做学员包。

应先在开发母版里验收案例数据。

本地启动：

```powershell
cd C:\Users\Admin\Documents\GitHub\video-fuke
python -m http.server 8000
```

浏览器打开：

```text
http://localhost:8000/web/index.html
```

重点验收：

1. 新案例能不能打开
2. 脚本 / 角色 / 场景 / 分镜是否完整
3. 提示词里有图1、图2、Image 时，左侧是否有输入图
4. 视频是否能播放
5. 视频是否压住文字
6. 分镜页是否能看到对应链路
7. 延长视频是否能看懂
8. 页面是否出现后台字段
9. `25cm` 是否没被影响

验收没问题后，再提交 `courseData.json`。

## 第 4 步：提交案例数据

如果本地验收通过，让 Codex 提交目标案例数据。

示例：

```bash
git add course-data/case-03/courseData.json
git commit -m "fix(case-03): clean course data and restore teaching chains"
```

提交前必须确认：

1. 没有误改 `25cm`
2. 没有误改 `web`
3. 没有误改 `scripts`
4. 没有误改 `source.json`
5. 没有误改 manifest / audit 文件
6. 没有误改图片 / 视频资源

## 第 5 步：启用 Skill 2，生成学员包与激活码流程

常用启用词：

```text
做学员包 case-03
```

或者：

```text
配置激活码 case-03
```

Codex 应读取：

```text
docs/video-fuke-student-package-activation-skill.md
```

然后按 Skill 2 处理学员交付。

Skill 2 应先确认：

1. `course-data/case-03/courseData.json` 已经存在
2. 案例数据已经验收通过
3. 不再修改 `courseData.json`
4. 学员包目录应该叫什么
5. 最终视频 mp4 是否已经准备好
6. 老师端激活码工具是否需要适配该案例

## 第 6 步：生成单案例学员包

学员包建议放在：

```text
packages/case-03-name/
```

学员包里应包含：

1. `start.bat`
2. `README.txt`
3. `web/`
4. `course-data/case-03/courseData.json`

学员包要求：

1. 只显示当前案例
2. 不显示 `25cm`
3. 不显示其他案例
4. 不要求学员安装 Git
5. 不要求学员克隆仓库
6. 使用独立端口
7. `start.bat` 必须从当前学员包目录启动
8. 如果端口被占用，要提示用户，不要打开错误页面
9. UI 保持既有风格，不重做页面

## 第 7 步：最终视频处理

最终视频推荐文件名：

```text
case-preview.mp4
```

推荐路径：

```text
packages/学员包名/web/assets/cases/case-xx/preview/case-preview.mp4
```

注意：

1. 如果最终视频在用户本地，但没有提交到 Git，远程 Claude / Codex 看不到。
2. 远程环境看不到 mp4 时，不要假装已经打进 zip。
3. 如果不想把 mp4 提交到 Git，可以由用户本地放进学员包后再压缩。
4. 打包前必须确认最终视频是否在学员包目录里。
5. 如果最终视频不存在，README 应提示应该把 mp4 放到哪里。

## 第 8 步：配置机器码 / 激活码流程

正式学员包不要使用普通共享课程密码。

不要使用：

```text
qifeng-2026
```

正式授权流程应为：

1. 老师给学员压缩包。
2. 压缩包可以由老师最后本地用 7-Zip 设置解压密码。
3. 学员用解压密码解压。
4. 学员双击 `start.bat`。
5. 页面显示机器码 / 设备码。
6. 学员复制机器码发给老师。
7. 老师使用老师端工具生成激活码。
8. 学员输入激活码。
9. 激活成功后进入课程。
10. 换电脑需要重新生成机器码和激活码。

学员包里的 `activation.config.js` 应确认：

1. `enabled` 为 `true`
2. `courseId` 是当前案例，例如 `case-03`
3. `devicePrefix` 与当前案例匹配
4. `publicKey` 与老师端私钥配对
5. 不配置普通 `password` 字段
6. `title` 显示当前课程名称

## 第 9 步：老师端激活码工具

老师端工具应放在：

```text
admin-tools/
```

或者：

```text
owner-tools/
```

不要放进学员包。

老师端工具要求：

1. 可以输入学员机器码
2. 可以选择或默认当前 `courseId`
3. 可以导入或粘贴老师私钥 JWK
4. 可以生成激活码
5. 可以复制激活码
6. 默认不要误用 `25cm` 的 `courseId`
7. 错误 `courseId` 生成的激活码不能激活当前案例

私钥管理规则：

1. 私钥不能放进 `packages/学员包`
2. 私钥不能进入最终学员 zip
3. 私钥不能提交到 GitHub
4. `.gitignore` 应保护私钥
5. 不要随便重新生成新密钥
6. 如果重新生成密钥，必须提醒旧激活码可能失效
7. 一个私钥可以用于多个课程，但激活码必须绑定不同 `courseId` 和 `deviceCode`

## 第 10 步：README 必须写清楚

每个学员包 README 必须写清楚：

1. 如何解压
2. 压缩包密码由老师提供
3. 如何启动 `start.bat`
4. 打开地址是什么
5. 页面会显示机器码
6. 如何复制机器码
7. 机器码发给谁
8. 老师返回激活码
9. 如何输入激活码
10. 激活失败怎么办
11. 换电脑需要重新激活
12. 不需要 Git
13. 不需要命令行基础
14. 所有内容本地运行，不上传云端
15. 端口被占用怎么办
16. Python 未安装怎么办
17. 如何清除本机已激活状态

README 不要写普通课程密码。

## 第 11 步：学员包本地验收

学员包生成后，必须本地验收。

示例：

双击：

```text
packages/学员包名/start.bat
```

浏览器应打开类似：

```text
http://127.0.0.1:独立端口/web/index.html
```

验收内容：

1. 页面只显示当前案例
2. 不显示 `25cm`
3. 不显示其他案例
4. 未激活前不能看到课程内容
5. 页面显示机器码
6. 可以复制机器码
7. 老师端工具能生成激活码
8. 正确激活码能进入课程
9. 错误激活码不能进入课程
10. 刷新后保持已激活
11. 清除 localStorage 后重新要求激活
12. 最终视频能播放
13. 脚本 / 角色 / 场景 / 分镜都能打开
14. 视频不压文字
15. 一键复制按钮还在
16. UI 风格没被重做

## 第 12 步：最终压缩包

最终压缩包应由用户在本地确认后生成。

推荐做法：

1. 确认最终视频已经放进学员包目录。
2. 确认激活码流程已经验收通过。
3. 打开学员包所在的上级目录。
4. 右键学员包文件夹。
5. 使用 7-Zip 添加到压缩包。
6. 设置解压密码。
7. 压缩包里最外层应该是一个文件夹。
8. 不要让文件解压后散落一地。

压缩包不能包含：

1. `.git`
2. `node_modules`
3. `admin-tools`
4. `owner-tools`
5. 老师端私钥
6. 其他案例数据
7. 整个开发仓库

压缩包解压密码由用户最后本地用 7-Zip 设置，不写进网页代码。

## 十三、推荐执行顺序

以后新案例推荐顺序：

1. 准备 `course-data/case-xx/source.json`
2. 启用 Skill 1：`复刻新视频 case-xx`
3. 生成 / 整理 `courseData.json`
4. 本地开发母版验收
5. 提交 `courseData.json`
6. 启用 Skill 2：`做学员包 case-xx`
7. 生成单案例学员包
8. 配置机器码 / 激活码
9. 放入最终视频
10. 本地验收学员包
11. 本地用 7-Zip 加解压密码
12. 发给学员

## 十四、常用启用词

### 启用 Skill 1

用于整理案例数据：

```text
复刻新视频 case-03
复刻这个视频 case-03
整理复刻案例 case-03
```

### 启用 Skill 2

用于做学员包和激活码：

```text
做学员包 case-03
配置激活码 case-03
准备发给学员 case-03
生成视频复刻学员包 case-03
```

## 十五、重要提醒

1. 不要把两个 Skill 混在一起。
2. 数据没验收通过前，不要做学员包。
3. 学员包没验收通过前，不要打最终 zip。
4. 私钥永远不能进学员包。
5. 最终视频如果只在本地、没有提交，远程环境看不到。
6. 本地能播放不等于远程 zip 已包含。
7. 压缩包解压密码最后由用户本地用 7-Zip 设置。
8. 正式学员包不使用普通课程密码。
9. 机器码 / 激活码流程必须在本地跑通后再发学员。
10. 每个新案例都要检查 `courseId`，不能误用 `25cm`。
