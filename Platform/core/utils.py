import logging
import redis
import json
import base64
import zlib
from django.conf import settings

# Redis client instance
redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    db=settings.REDIS_DB
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def print_debug(*args, **kwargs):
    """Global debug logging helper."""
    if settings.DEBUG:
        message = " ".join(map(str, args)) + " ".join(
            f"{k}={v}" for k, v in kwargs.items()
        )
        logger.info(message)

def print_json_debug(message):
    """Pretty-print JSON debug messages with truncation."""
    truncator = 50
    if not isinstance(message, dict):
        print_debug(message)
        return
        
    truncated_message = {
        k: (
            str(v)[:truncator] + "..."
            if hasattr(v, "__getitem__") and len(str(v)) > truncator
            else v
        )
        for k, v in message.items()
    }
    print_debug(json.dumps(truncated_message, indent=4))

def decompress_json_data(compressed_data):
    """Base64 decode and zlib decompress JSON data."""
    try:
        compressed_bytes = base64.b64decode(compressed_data)
        decompressed_bytes = zlib.decompress(compressed_bytes).decode("utf-8")
        return json.loads(decompressed_bytes)
    except Exception as e:
        logger.error(f"Decompression error: {str(e)}")
        return None
