老师端 · 激活码工具
==========================================

⚠ 本目录里的内容是老师私有的，绝对不要打进学员包，也不要把
   private-key.local.json 提交到 git 或发给任何学员。

------------------------------------------------------------
▶ 文件说明
------------------------------------------------------------

  sign-license.py        签名脚本（核心）
  gen-keypair.py         一次性密钥生成器
  生成激活码.bat         Windows 一键签名（最常用）
  private-key.local.json 私钥（git 忽略，不存在时需自己生成或导入）
  README.txt             本说明

------------------------------------------------------------
▶ 一次性准备
------------------------------------------------------------

1) 安装 Python 3 + 依赖：

       pip install cryptography

2) 准备私钥。两种情况：

   情况 A：你已经有 owner-tools/ 里原来的私钥
   --------------------------------------------
   把它转成 JWK 格式（包含 d、x、y 三个 base64url 字段）并保存为：

       admin-tools/private-key.local.json

   如果你原来的私钥已经是 JWK，直接改名复制过来即可。

   情况 B：你没有匹配 web/activation.config.js 中 publicKey 的私钥
   ----------------------------------------------------------------
   说明你弄丢了，或这台机器是新装的。运行：

       python gen-keypair.py

   这会：
   - 写一份新私钥到 admin-tools/private-key.local.json
   - 把对应的新 publicKey 块打印到屏幕

   然后把屏幕上的 publicKey 块完整粘贴到：

       web/activation.config.js                              （开发母版）
       packages/qifeng-zhishi/web/activation.config.js       （起风之时学员包）
       未来其它案例的 activation.config.js

   覆盖里面原有的 publicKey 字段。

   注意：换密钥后，之前发出的所有旧激活码立刻失效，所有学员需要
   重新获取激活码。仅在确实必要时换。

------------------------------------------------------------
▶ 日常给学员发激活码
------------------------------------------------------------

收到学员发来的机器码（形如 QIFENG-AB12-CD34-EF56）后：

  双击 生成激活码.bat
  输入课程 ID：case-02
  输入机器码：QIFENG-AB12-CD34-EF56
  屏幕会输出一行很长的字符串，例如：
      eyJjb3Vyc2VJZCI6...gT9_aA.MEUC...zXZw

把那一整行（注意中间的"."不要丢）发给学员粘贴即可。

也可以命令行直接调用：

    python sign-license.py --course case-02 --device QIFENG-AB12-CD34-EF56

------------------------------------------------------------
▶ 激活码的约束
------------------------------------------------------------

  - 激活码与机器码一一绑定（同一台机器才能用）。
  - 激活码与课程 ID 绑定（case-02 的激活码不能用于 25cm，反之亦然）。
  - 激活码本身没有过期时间（payload 里有 issuedAt，但前端没校验
    过期）。如需启用过期，需要改 web/activation.js 中 verifyLicense。

------------------------------------------------------------
▶ 测试激活码生成
------------------------------------------------------------

  # 准备好私钥后，用任意伪机器码试一下：
  python sign-license.py --course case-02 --device QIFENG-TEST-TEST-TEST

  # 输出形如：
  # eyJjb3Vyc2VJZCI6ImNhc2UtMDIiLCJkZXZpY2VDb2RlIjoiUUlGRU5HLVRFU1QtVEVTVC1URVNUIiwiaXNzdWVkQXQiOjE3MDAwMDAwMDAwMDB9.AbCdEf...

  这串就是激活码。学员粘贴后会看到"激活码无效，或不属于当前设备"
  —— 因为机器码是假的。这只是验证你的签名链路 OK。
