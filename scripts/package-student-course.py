#!/usr/bin/env python3
"""Check and package a single-case video-fuke student course.

The script is intentionally strict: it must not silently create an
unencrypted delivery zip, and it must not package teacher-side secrets.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


REQUIRED_FILES = [
    "start.bat",
    "README.txt",
    "web/index.html",
    "web/app.js",
    "web/styles.css",
    "web/courses.json",
    "web/activation.js",
    "web/activation.css",
    "web/activation.config.js",
]

FORBIDDEN_DIR_NAMES = {
    ".git",
    "node_modules",
    "admin-tools",
    "owner-tools",
    "dist",
    "__pycache__",
}

FORBIDDEN_FILE_NAMES = {
    ".DS_Store",
}

FORBIDDEN_GLOBS = [
    "*.local.*",
    "~$*",
    "*.tmp",
    "*.temp",
]

COMMON_7Z_PATHS = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
]


class PackageError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查并生成视频复刻学员交付 zip（默认必须使用 7-Zip 加密）。"
    )
    parser.add_argument("--package-dir", required=True, help="学员包目录，例如 packages/qifeng-zhishi")
    parser.add_argument("--output", required=True, help="输出 zip 路径，例如 dist/qifeng-zhishi-student-package.zip")
    parser.add_argument("--password", default="", help="压缩包解压密码；不会写入文件或报告")
    parser.add_argument("--require-video", action="store_true", help="要求最终视频必须存在")
    parser.add_argument("--course-id", required=True, help="课程 ID，例如 case-02")
    parser.add_argument("--expected-title", default="", help="期望课程标题，用于核对 courses.json")
    parser.add_argument(
        "--allow-no-password",
        action="store_true",
        help="显式允许生成无密码 zip；默认不允许，仅用于特殊本地检查",
    )
    parser.add_argument("--check-only", action="store_true", help="只检查，不生成 zip")
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    return text


def js_bool(text: str, key: str) -> bool | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(true|false)\b", text)
    if not match:
        return None
    return match.group(1) == "true"


def js_string(text: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(['\"])(.*?)\1", text, flags=re.S)
    if not match:
        return None
    return match.group(2)


def has_js_property(text: str, key: str) -> bool:
    return re.search(rf"\b{re.escape(key)}\s*:", text) is not None


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - show path and original parse error
        raise PackageError(f"JSON 解析失败：{path}；{exc}") from exc


def fail_if_missing(package_dir: Path, rel_path: str, checks: list[str]) -> Path:
    path = package_dir / rel_path
    if not path.exists():
        raise PackageError(f"缺少必要文件：{path}")
    checks.append(f"OK: 找到 {rel_path}")
    return path


def iter_package_paths(package_dir: Path):
    for root, dirs, files in os.walk(package_dir):
        root_path = Path(root)
        for dirname in list(dirs):
            yield root_path / dirname
        for filename in files:
            yield root_path / filename


def is_forbidden_local_file(path: Path) -> bool:
    name = path.name
    if name in FORBIDDEN_FILE_NAMES:
        return True
    lower_name = name.lower()
    if "private-key" in lower_name or lower_name.startswith("private_key"):
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in FORBIDDEN_GLOBS)


def check_forbidden_content(package_dir: Path, checks: list[str]) -> None:
    risks: list[str] = []
    for path in iter_package_paths(package_dir):
        rel = path.relative_to(package_dir)
        parts = {part.lower() for part in rel.parts}
        if parts & FORBIDDEN_DIR_NAMES:
            risks.append(str(rel))
            continue
        if path.is_file() and is_forbidden_local_file(path):
            risks.append(str(rel))
    if risks:
        preview = "\n  - ".join(risks[:30])
        raise PackageError(f"学员包包含禁止打包内容：\n  - {preview}")
    checks.append("OK: 未发现 .git / node_modules / admin-tools / owner-tools / private-key 风险")


def check_courses(package_dir: Path, course_id: str, expected_title: str, checks: list[str]) -> dict:
    courses_path = fail_if_missing(package_dir, "web/courses.json", checks)
    data = load_json(courses_path)
    if not isinstance(data, dict) or not isinstance(data.get("courses"), list):
        raise PackageError("web/courses.json 结构不正确：缺少 courses 数组")
    courses = data["courses"]
    ids = [course.get("id") for course in courses if isinstance(course, dict)]
    if ids != [course_id]:
        raise PackageError(f"web/courses.json 必须只包含当前课程 {course_id}，当前为：{ids}")
    raw_text = courses_path.read_text(encoding="utf-8")
    if "25cm" in ids or '"25cm"' in raw_text:
        raise PackageError("web/courses.json 中发现 25cm，不能进入单案例学员包")
    if "真人视频拆解 01" in raw_text:
        raise PackageError("web/courses.json 中发现“真人视频拆解 01”，疑似旧课程残留")
    course = courses[0]
    if expected_title and course.get("title") != expected_title:
        raise PackageError(
            f"课程标题不匹配：期望 {expected_title!r}，实际 {course.get('title')!r}"
        )
    checks.append(f"OK: web/courses.json 只包含 {course_id}")
    return course


def check_activation(package_dir: Path, course_id: str, checks: list[str]) -> dict:
    config_path = fail_if_missing(package_dir, "web/activation.config.js", checks)
    clean = strip_js_comments(config_path.read_text(encoding="utf-8"))
    enabled = js_bool(clean, "enabled")
    config_course_id = js_string(clean, "courseId")
    device_prefix = js_string(clean, "devicePrefix")
    if enabled is not True:
        raise PackageError("activation.config.js 必须设置 enabled: true")
    if config_course_id != course_id:
        raise PackageError(
            f"activation.config.js courseId 必须是 {course_id}，当前为 {config_course_id!r}"
        )
    if has_js_property(clean, "password"):
        raise PackageError("activation.config.js 不应配置普通 password 字段")
    if not has_js_property(clean, "publicKey"):
        raise PackageError("activation.config.js 缺少 publicKey")
    if not device_prefix:
        raise PackageError("activation.config.js 缺少 devicePrefix")
    checks.append("OK: activation.config.js 已启用机器码 / 激活码流程")
    return {
        "enabled": enabled,
        "courseId": config_course_id,
        "devicePrefix": device_prefix,
        "hasPassword": False,
        "hasPublicKey": True,
    }


def check_readme(package_dir: Path, checks: list[str]) -> None:
    readme_path = fail_if_missing(package_dir, "README.txt", checks)
    text = readme_path.read_text(encoding="utf-8")
    if "qifeng-2026" in text:
        raise PackageError("README.txt 不能写普通课程密码 qifeng-2026")
    if "机器码" not in text or "激活码" not in text:
        raise PackageError("README.txt 必须包含机器码 / 激活码流程说明")
    if "解压" not in text or "密码" not in text or "老师" not in text:
        raise PackageError("README.txt 必须说明压缩包密码由老师提供")
    checks.append("OK: README.txt 包含正式机器码 / 激活码流程")


def check_course_data(package_dir: Path, course_id: str, checks: list[str]) -> Path:
    if (package_dir / "course-data" / "25cm").exists():
        raise PackageError("学员包中发现 course-data/25cm，不能进入单案例包")
    path = package_dir / "course-data" / course_id / "courseData.json"
    if not path.exists():
        raise PackageError(f"缺少课程数据：{path}")
    load_json(path)
    checks.append(f"OK: 找到并解析 course-data/{course_id}/courseData.json")
    return path


def check_video(package_dir: Path, course_id: str, require_video: bool, checks: list[str]) -> tuple[Path, bool]:
    path = package_dir / "web" / "assets" / "cases" / course_id / "preview" / "case-preview.mp4"
    exists = path.exists()
    if require_video and not exists:
        raise PackageError(
            "缺少最终视频：\n"
            f"{path}\n"
            "请先把最终视频改名为 case-preview.mp4 放到该路径后再运行脚本。"
        )
    checks.append(("OK" if exists else "WARN") + f": 最终视频路径 {path}")
    return path, exists


def check_package(package_dir: Path, course_id: str, expected_title: str, require_video: bool) -> dict:
    checks: list[str] = []
    if not package_dir.exists() or not package_dir.is_dir():
        raise PackageError(f"学员包目录不存在：{package_dir}")
    if (package_dir / ".git").exists():
        raise PackageError("package-dir 不能是整个开发仓库或包含 .git 的目录")

    for rel_path in REQUIRED_FILES:
        fail_if_missing(package_dir, rel_path, checks)

    course = check_courses(package_dir, course_id, expected_title, checks)
    activation = check_activation(package_dir, course_id, checks)
    check_readme(package_dir, checks)
    course_data_path = check_course_data(package_dir, course_id, checks)
    video_path, has_video = check_video(package_dir, course_id, require_video, checks)
    check_forbidden_content(package_dir, checks)

    return {
        "checks": checks,
        "course": course,
        "activation": activation,
        "courseDataPath": course_data_path,
        "videoPath": video_path,
        "hasVideo": has_video,
    }


def find_7z() -> str | None:
    for name in ("7z", "7z.exe"):
        found = shutil.which(name)
        if found:
            return found
    for value in COMMON_7Z_PATHS:
        path = Path(value)
        if path.exists():
            return str(path)
    return None


def ensure_output_path(output: Path, package_dir: Path) -> None:
    try:
        output.relative_to(package_dir)
    except ValueError:
        pass
    else:
        raise PackageError("输出 zip 不能放在学员包目录内部，避免把 zip 打进自己")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()


def package_with_7z(package_dir: Path, output: Path, password: str) -> None:
    seven_zip = find_7z()
    if not seven_zip:
        raise PackageError(
            "未找到 7-Zip，无法生成带密码 zip。\n"
            "请安装 7-Zip，或把 7z.exe 加入 PATH，下载后重新运行本脚本。"
        )
    ensure_output_path(output, package_dir)
    command = [
        seven_zip,
        "a",
        "-tzip",
        str(output),
        package_dir.name,
        f"-p{password}",
        "-mem=AES256",
        "-y",
        "-xr!.git",
        "-xr!node_modules",
        "-xr!admin-tools",
        "-xr!owner-tools",
        "-xr!dist",
        "-xr!__pycache__",
        "-xr!.DS_Store",
        "-xr!*private-key*",
        "-xr!*.local.*",
        "-xr!*.tmp",
        "-xr!*.temp",
    ]
    result = subprocess.run(
        command,
        cwd=str(package_dir.parent),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise PackageError("7-Zip 打包失败：\n" + result.stdout[-3000:])
    if not output.exists():
        raise PackageError("7-Zip 未生成输出文件")


def package_without_password(package_dir: Path, output: Path) -> None:
    ensure_output_path(output, package_dir)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in iter_package_paths(package_dir):
            if path.is_dir():
                continue
            rel = path.relative_to(package_dir.parent)
            rel_parts = {part.lower() for part in rel.parts}
            if rel_parts & FORBIDDEN_DIR_NAMES:
                continue
            if is_forbidden_local_file(path):
                continue
            zf.write(path, rel.as_posix())


def format_size(path: Path) -> str:
    size = path.stat().st_size
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def print_report(args: argparse.Namespace, package_dir: Path, output: Path, result: dict, zipped: bool, encrypted: bool) -> None:
    activation = result["activation"]
    print("\n=== 学员交付包检查报告 ===")
    print(f"学员包目录: {package_dir}")
    print(f"courseId: {args.course_id}")
    print(f"课程标题: {args.expected_title or result['course'].get('title', '')}")
    print("start.bat: OK")
    print("README: OK")
    print("courses.json 只包含当前案例: OK")
    print(f"activation 已启用: {activation['enabled']}")
    print("机器码 / 激活码流程: OK")
    print(f"发现普通 password 字段: {activation['hasPassword']}")
    print(f"最终视频: {'存在' if result['hasVideo'] else '未放置'}")
    print("私钥风险: 未发现")
    print("25cm: 未发现")
    print("admin-tools / owner-tools: 未发现")
    print(f"zip 输出路径: {output}")
    if zipped:
        print(f"zip 文件大小: {format_size(output)}")
    else:
        print("zip 文件大小: 未生成")
    print(f"已设置压缩包密码: {'是' if encrypted else '否'}")
    print("\n检查明细:")
    for item in result["checks"]:
        print(f"- {item}")
    print("\n学员启动方式:")
    print("1. 解压 zip。")
    print("2. 输入老师提供的解压密码。")
    print(f"3. 双击 {package_dir.name}/start.bat。")
    print("4. 页面显示机器码。")
    print("5. 把机器码发给老师。")
    print("6. 老师生成激活码。")
    print("7. 学员输入激活码进入课程。")


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    package_dir = resolve_path(args.package_dir, repo_root)
    output = resolve_path(args.output, repo_root)

    try:
        if not args.password and not args.allow_no_password and not args.check_only:
            raise PackageError("必须通过 --password 提供压缩包解压密码；脚本不会生成无密码 zip")
        result = check_package(package_dir, args.course_id, args.expected_title, args.require_video)
        if args.check_only:
            print_report(args, package_dir, output, result, zipped=False, encrypted=False)
            print("\n结果: 仅检查完成，未生成 zip。")
            return 0
        if args.password:
            package_with_7z(package_dir, output, args.password)
            print_report(args, package_dir, output, result, zipped=True, encrypted=True)
        else:
            package_without_password(package_dir, output)
            print_report(args, package_dir, output, result, zipped=True, encrypted=False)
            print("\nWARN: 已按 --allow-no-password 生成无密码 zip。正式交付不推荐这样做。")
        print("\n结果: 学员交付包生成完成。")
        return 0
    except PackageError as exc:
        print("\nERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
