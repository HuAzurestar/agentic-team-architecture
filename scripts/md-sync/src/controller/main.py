"""Central controller entry point."""
from pathlib import Path
import argparse

from src.config.loader import load_config
from src.controller.sync_controller import SyncController


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote-authoritative Markdown sync controller")
    parser.add_argument("command", choices=["status", "download", "upload", "sync-from-remote", "sync-to-remote"])
    parser.add_argument("file", nargs="?")
    parser.add_argument("--remote", help="兼容旧下载格式，例如 youtrack_article:DEMO-A-1")
    parser.add_argument("--target", help="创建目标，例如 youtrack/issue/DEMO")
    args = parser.parse_args()
    config = load_config(Path(__file__).resolve().parents[2] / "config")
    controller = SyncController(config)
    if args.command == "status":
        controller.status()
    elif not args.file:
        parser.error("download/upload 需要指定 Markdown 文件")
    elif args.command in ("sync-from-remote", "download"):
        controller.download(Path(args.file), args.remote)
    else:
        result = controller.upload(Path(args.file), args.target)
        print(result if isinstance(result, dict) else result.status.value)


if __name__ == "__main__":
    main()
