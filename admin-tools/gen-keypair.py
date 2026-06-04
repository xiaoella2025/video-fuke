#!/usr/bin/env python3
"""老师端：生成一对 ECDSA P-256 密钥（JWK）。

只在以下情况运行：
  1) 第一次部署、还没有任何私钥；或
  2) 旧私钥丢了，需要换一对（注意：换密钥后所有已发出的旧激活码失效，
     且必须把新公钥同步到每个学员包的 activation.config.js）。

输出：
  - 私钥写入 admin-tools/private-key.local.json（已在 .gitignore 中排除）
  - 公钥块打印到屏幕，请人工复制到 web/activation.config.js 和
    packages/<案例>/web/activation.config.js 的 publicKey 字段。
"""
import base64
import json
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:
    sys.exit("缺少依赖。请先执行：pip install cryptography")


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def main():
    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_numbers = private_key.private_numbers()
    pub_numbers = priv_numbers.public_numbers
    x = pub_numbers.x.to_bytes(32, "big")
    y = pub_numbers.y.to_bytes(32, "big")
    d = priv_numbers.private_value.to_bytes(32, "big")

    private_jwk = {
        "kty": "EC", "crv": "P-256",
        "x": b64url(x), "y": b64url(y), "d": b64url(d),
        "ext": True, "key_ops": ["sign"],
    }
    public_jwk = {
        "kty": "EC", "crv": "P-256",
        "x": b64url(x), "y": b64url(y),
        "ext": True, "key_ops": ["verify"],
    }

    out = Path(__file__).parent / "private-key.local.json"
    if out.exists():
        print(f"[!] {out} 已存在，未覆盖。如确认要换密钥，请先手动重命名旧文件。")
        return
    out.write_text(json.dumps(private_jwk, indent=2))
    print(f"[ok] 私钥已写入：{out}（受 .gitignore 保护，不会被提交）")
    print()
    print("把下面这块 publicKey 复制到 activation.config.js 的 publicKey 字段：")
    print("------------------------------------------------------------------")
    print(json.dumps(public_jwk, indent=2, ensure_ascii=False))
    print("------------------------------------------------------------------")


if __name__ == "__main__":
    main()
