#!/usr/bin/env python3
"""
配置生成 CLI — 从 Profile 生成部署所需的所有配置文件。

用法:
  # 生成 Docker 部署配置（默认）
  python configs/generate_config.py --profile multi-gpu

  # 生成 Docker 部署配置（单卡）
  python configs/generate_config.py --profile single-gpu --mode docker

  # 生成原生部署配置
  python configs/generate_config.py --profile multi-gpu --mode native

  # 列出所有可用 profile
  python configs/generate_config.py --list

  # 指定输出目录
  python configs/generate_config.py --profile single-gpu --output /tmp/kb-config
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from configs.profile_loader import (
    load_profile,
    generate_env,
    generate_docker_override,
    generate_supervisord,
    generate_systemd_units,
)
from configs.profile_schema import ProfileSpec


def list_profiles(profiles_dir: str) -> None:
    """列出所有可用的 profile 文件"""
    profiles_path = Path(profiles_dir)
    if not profiles_path.exists():
        print(f"[ERROR] Profiles 目录不存在: {profiles_dir}")
        sys.exit(1)

    yaml_files = sorted(profiles_path.glob("*.yaml")) + sorted(profiles_path.glob("*.yml"))
    if not yaml_files:
        print(f"[WARN] 未找到 profile 文件: {profiles_dir}")
        return

    print("可用的硬件 Profile:")
    for f in yaml_files:
        try:
            prof = load_profile(str(f))
            print(f"  {prof.profile.name:<20s} — {prof.profile.description}")
            gpu_info = f"{prof.gpus.count}×{prof.gpus.models[0]}" if prof.gpus.models else f"{prof.gpus.count}×GPU"
            print(f"    GPU: {gpu_info}, LLM: {prof.services.llm.model}")
        except Exception as e:
            print(f"  {f.stem:<20s} — [ERROR] 加载失败: {e}")


def generate_all(profile: ProfileSpec, mode: str, output_dir: str) -> dict[str, str]:
    """生成所有配置文件，返回 {文件名: 内容} 映射"""
    files: dict[str, str] = {}

    # .env 始终生成
    files[".env"] = generate_env(profile)

    if mode == "docker":
        files["docker-compose.override.yml"] = generate_docker_override(profile)
    elif mode == "native":
        files["supervisord.conf"] = generate_supervisord(profile, project_dir=str(PROJECT_DIR))
        units = generate_systemd_units(profile, project_dir=str(PROJECT_DIR))
        for name, content in units.items():
            files[f"systemd/{name}.service"] = content
    else:
        print(f"[ERROR] 未知部署模式: {mode} (支持: docker, native)")
        sys.exit(1)

    return files


def write_files(files: dict[str, str], output_dir: str, force: bool = False) -> None:
    """写入生成的文件到磁盘"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        dest = out / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists() and not force:
            print(f"  [SKIP] {rel_path} 已存在（使用 --force 强制覆盖）")
            continue

        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [OK]   {rel_path}")


def main():
    parser = argparse.ArgumentParser(
        description="从硬件 Profile 生成部署配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --profile multi-gpu                     # 默认生成 Docker 部署配置
  %(prog)s --profile single-gpu --mode native      # 生成原生部署配置
  %(prog)s --list                                  # 列出所有可用 profile
  %(prog)s --profile multi-gpu --force             # 强制覆盖已有文件
        """,
    )
    parser.add_argument(
        "--profile", "-p",
        help="Profile 名称 (如 single-gpu) 或 .yaml 文件路径",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["docker", "native"],
        default="docker",
        help="部署模式 (默认: docker)",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(PROJECT_DIR),
        help=f"输出目录 (默认: 项目根目录)",
    )
    parser.add_argument(
        "--profiles-dir",
        default=str(PROJECT_DIR / "configs" / "profiles"),
        help="Profiles 目录路径",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有可用 profile",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制覆盖已有文件",
    )

    args = parser.parse_args()

    # --list 模式
    if args.list:
        list_profiles(args.profiles_dir)
        return

    # 需要 --profile
    if not args.profile:
        parser.error("需要指定 --profile（或使用 --list 查看可用选项）")

    # 加载 profile
    print(f"[INFO] 加载 Profile: {args.profile}")
    try:
        profile = load_profile(args.profile, profiles_dir=args.profiles_dir)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Profile 验证失败: {e}")
        sys.exit(1)

    print(f"[INFO] 硬件: {profile.gpus.count}×GPU, LLM: {profile.services.llm.model}")
    print(f"[INFO] 部署模式: {args.mode}")
    print(f"[INFO] 输出目录: {args.output}")
    print()

    # 生成配置
    print("生成配置文件:")
    files = generate_all(profile, args.mode, args.output)

    # 写入
    if args.output != str(PROJECT_DIR) or args.mode != "docker":
        suffix = f"-{args.mode}"
    else:
        suffix = ""
    write_files(files, args.output, force=args.force)

    print()
    if args.mode == "docker":
        print(f"[INFO] 配置生成完成。运行 'make start' 启动服务。")
    else:
        print(f"[INFO] 配置生成完成。")
        print(f"[INFO] 启动原生服务: bash scripts/native/start_all.sh")
        print(f"[INFO] 或安装 systemd 单元: bash scripts/native/install_systemd.sh")


if __name__ == "__main__":
    main()
