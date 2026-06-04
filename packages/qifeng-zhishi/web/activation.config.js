// 起风之时 · 学员包 · 访问密码配置
//
// ▶ 修改密码：把下面 password 字段的字符串改成新密码即可。
//   旧密码已经解锁过的浏览器不会自动重新弹密码门 —— 让学员清一下
//   localStorage（详见 README.txt "如何清除已解锁状态"）即可。
//
// ▶ 关闭密码门：把 enabled 改为 false。
//
// 注意：这是本地静态密码，不接服务器、不上云端。该文件可被打开查看。
window.activation = {
  enabled: true,
  // ↓↓↓ 改这里更换密码 ↓↓↓
  password: "qifeng-2026",
  // 显示文案
  title: "动漫视频拆解 01｜起风之时 · 课程访问",
  passwordHint: "请向老师获取访问密码。",
  // localStorage 隔离用，不要轻易改
  courseId: "case-02",
  devicePrefix: "QIFENG",
  // 兼容字段：密码模式下不使用，但保留以匹配 activation.js 的旧授权流程
  publicKey: {
    kty: "EC",
    crv: "P-256",
    x: "n67_c_v4OOifqlxNhR5i8Chkj5kgsvtTcoGXI9z8slk",
    y: "WEeTa6PzoUttzugABCl4R_KDS8Kt_h0bfXsrg26ziHg",
    ext: true,
    key_ops: ["verify"],
  },
};
