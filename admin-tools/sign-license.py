#!/usr/bin/env python3
"""老师端：根据学员发来的机器码，生成可解锁课程的激活码。

输出格式与 web/activation.js 中 verifyLicense 严格一致：
    license = base64url(payload).base64url(signature)
其中：
    payload   = {"courseId": str, "deviceCode": str, "issuedAt": int_ms}
    signature = ECDSA(P-256, SHA-256) 对 base64url(payload) 文本字节的签名，
                输出 IEEE P1363 格式（r||s，64 字节），再 base64url。
私钥从同目录的 private-key.local.json 读取（JWK 格式，包含 d/x/y）。

用法示例：
    python sign-license.py --course case-02 --device QIFENG-XXXX-XXXX-XXXX

如果你已经有其它格式的私钥（PEM / OpenSSH 等），可以先转成 JWK，
或者改用你原有的 owner-tools/ 签名脚本，只要 courseId 用 case-02 即可。
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
except ImportError:
    sys.exit("缺少依赖。请先执行：pip install cryptography")


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def load_private_key(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for k in ("d", "x", "y"):
        if k not in data:
            sys.exit(f"私钥文件缺少字段 {k!r}：{path}")
    d_int = int.from_bytes(b64url_decode(data["d"]), "big")
    return ec.derive_private_key(d_int, ec.SECP256R1())


def sign(private_key, course_id: str, device_code: str) -> str:
    payload = {
        "courseId": course_id,
        "deviceCode": device_code,
        "issuedAt": int(time.time() * 1000),
    }
    body_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body_b64 = b64url(body_json)
    sig_der = private_key.sign(body_b64.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(sig_der)
    sig_p1363 = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{body_b64}.{b64url(sig_p1363)}"


def main():
    ap = argparse.ArgumentParser(description="为学员机器码生成激活码")
    ap.add_argument("--course", required=True, help="课程 ID，如：case-02 或 25cm")
    ap.add_argument("--device", required=True, help="学员发来的机器码，如：QIFENG-XXXX-XXXX-XXXX")
    ap.add_argument(
        "--key",
        default="private-key.local.json",
        help="JWK 私钥文件路径（默认：admin-tools/private-key.local.json）",
    )
    args = ap.parse_args()

    key_path = Path(args.key)
    if not key_path.is_absolute():
        key_path = Path(__file__).parent / key_path
    if not key_path.exists():
        sys.exit(
            f"未找到私钥文件：{key_path}\n"
            f"请先把你原有的 JWK 私钥放到该路径，或运行：\n"
            f"    python gen-keypair.py\n"
            f"生成新密钥（注意：换密钥后必须同步更新学员包里的 publicKey！）"
        )

    private_key = load_private_key(key_path)
    license_str = sign(private_key, args.course, args.device)
    print(license_str)


if __name__ == "__main__":
    main()
