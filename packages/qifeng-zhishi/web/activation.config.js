// 起风之时 · 学员包 · 激活配置
//
// 正式流程：ECDSA 设备绑定授权码（不是共享密码）。
//   学员打开页面 → 看到本机机器码 →
//   把机器码发给老师 → 老师用 admin-tools/sign-license.py 生成激活码 →
//   学员粘贴激活码 → 解锁课程。
//
// publicKey 必须与老师私钥配对，二者一改全改。
// 切勿把对应的私钥放进本目录或任何学员包目录。
window.activation = {
  enabled: true,
  // 给页面顶部 + 激活面板用的标题（不影响下方教学 UI）
  title: "动漫视频拆解 01｜起风之时 · 课程激活",
  // 课程 ID（必须与激活码 payload.courseId 一致；用于隔离 localStorage 与
  // 老师签名时的 --course 参数）
  courseId: "case-02",
  // 机器码前缀：影响学员看到的设备码长相，如 QIFENG-AB12-CD34-EF56
  devicePrefix: "QIFENG",
  // ECDSA P-256 公钥（JWK）。必须与老师手中私钥配对。
  publicKey: {
    kty: "EC",
    crv: "P-256",
    x: "n67_c_v4OOifqlxNhR5i8Chkj5kgsvtTcoGXI9z8slk",
    y: "WEeTa6PzoUttzugABCl4R_KDS8Kt_h0bfXsrg26ziHg",
    ext: true,
    key_ops: ["verify"],
  },
};
