import logging
from django.conf import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def print_debug(*args, **kwargs):
    if settings.DEBUG:
        message = " ".join(map(str, args)) + " ".join(
            f"{k}={v}" for k, v in kwargs.items()
        )
        logger.info(message)