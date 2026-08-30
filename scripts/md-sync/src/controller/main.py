"""Central controller entry point."""
from pathlib import Path
import argparse
import sys

from src.config.loader import load_config
from src.controller.sync_controller import SyncController
from src.core.logging import get_logger


def main() -> None:
    # Keep one CLI entry point so every operation receives the same config,
    # argument logging, validation, and error reporting behavior.
    parser = argparse.ArgumentParser(description="Remote-authoritative Markdown sync controller")
    parser.add_argument("command", choices=["status", "download", "upload", "sync-from-remote", "sync-to-local", "sync-to-remote"])
    parser.add_argument("file", nargs="?")
    parser.add_argument("--remote", help="兼容旧下载格式，例如 youtrack_article:DEMO-A-1")
    parser.add_argument("--target", help="创建目标，例如 youtrack/issue/DEMO")
    # Safe mode is the default; --joint explicitly opts into extended fields.
    parser.add_argument("--joint", action="store_true", help="sync extended fields")
    args = parser.parse_args()
    logger = get_logger("python " + " ".join(sys.argv))
    logger.info("cli_start command=%s file=%s remote=%s target=%s", args.command, args.file, args.remote, args.target)
    def log_uncaught(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("cli_error command=%s file=%s remote=%s target=%s", args.command, args.file, args.remote, args.target, exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = log_uncaught
    config = load_config(Path(__file__).resolve().parents[2] / "config")
    controller = SyncController(config)
    if args.command == "status":
        controller.status()
    elif not args.file:
        parser.error("download/upload 需要指定 Markdown 文件")
    elif args.command in ("sync-from-remote", "sync-to-local", "download"):
        controller.download(Path(args.file), args.remote)
    elif args.command == "sync-to-remote":
        result = controller.sync_to_remote(Path(args.file), joint=args.joint)
        print(result)
    else:
        result = controller.upload(Path(args.file), args.target)
        print(result if isinstance(result, dict) else result.status.value)


if __name__ == "__main__":
    main()
