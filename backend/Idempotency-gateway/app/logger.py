import logging
import sys


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


class ExtraContextLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.pop("extra", {})
        if extra:
            msg = f"{msg} | {extra}"
        return msg, kwargs


def get_logger(name: str) -> ExtraContextLogger:
    return ExtraContextLogger(logging.getLogger(name), {})