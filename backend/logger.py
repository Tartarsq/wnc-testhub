import logging
from pathlib import Path


def create_logger(log_folder: Path) -> logging.Logger:
    """
    Create a logger that writes to both the terminal and a file.
    """
    log_folder.mkdir(parents=True, exist_ok=True)
    log_file = log_folder / "test_session.log"

    logger = logging.getLogger("wnc_testhub")
    logger.setLevel(logging.INFO)

    # Prevent duplicate messages if the program is run more than once.
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger