import logging
import sys
from datetime import datetime
from pathlib import Path

def get_logger(cli_args: str | None = None) -> logging.Logger:
    logger = logging.getLogger("md-sync")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    stamp = datetime.now().strftime("%Y%m%d.%H%M%S.%f")[:20]
    path = Path(__file__).resolve().parents[2] / "logs" / f"md-sync.{stamp}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.ERROR)
    console.setFormatter(formatter)
    logger.addHandler(console)
    if cli_args:
        logger.info("CLI ARGS: %s", cli_args)
    return logger
