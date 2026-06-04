视频复刻 · 起风之时 · 学员包
==============================

▶ 使用方法（Windows）

1. 把这个文件夹整体放到一个英文路径下（避免中文路径出问题）。
2. 双击 start.bat。
3. 浏览器会自动打开，进入"动漫视频拆解 01｜起风之时"案例。
4. 用完直接关闭弹出的黑色命令行窗口，即停止服务。

需要：Python 3（首次使用如未安装，按 start.bat 提示去 python.org 下载，
安装时勾选 "Add Python to PATH"）。

▶ 顶部"拆解的案例视频"如何接入

请把《起风之时》最终视频文件命名为 case-preview.mp4，放到：

    web/assets/cases/case-02/preview/case-preview.mp4

放好之后刷新页面即可播放。文件未放置时，页面会显示
"案例视频待上传"占位，并提示需要放到的路径，不会报错。

▶ 文件结构

    start.bat                    一键启动
    README.txt                   说明（本文件）
    web/                         教学网页
      index.html                 入口
      courses.json               单案例配置
      assets/cases/case-02/preview/   ← 最终视频放这里
    course-data/case-02/         课程数据

▶ 注意

- 本包只包含《起风之时》案例。
- 不需要 Git，不需要安装额外软件，不要修改 courses.json。
- 学员练习数据保存在浏览器本地（同一浏览器换案例也不会丢）。
