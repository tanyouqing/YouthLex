import logging


def configure_logging(log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    normalized_level = getattr(logging, log_level.upper(), logging.INFO)

    if not root_logger.handlers:
        logging.basicConfig(
            level=normalized_level,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    else:
        root_logger.setLevel(normalized_level)
        for handler in root_logger.handlers:
            handler.setLevel(normalized_level)
