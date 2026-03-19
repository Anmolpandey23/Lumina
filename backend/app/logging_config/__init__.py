"""
Logging configuration for the backend
"""

import os
from typing import Dict


def setup_logging() -> Dict:
    """Configure logging for the application"""
    
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "detailed",
                "filename": os.getenv("LOG_FILE", "app.log"),
                "maxBytes": int(os.getenv("LOG_MAX_BYTES", "10485760")),  # 10MB
                "backupCount": int(os.getenv("LOG_BACKUP_COUNT", "5"))
            }
        },
        "loggers": {
            "": {
                "level": log_level,
                "handlers": ["console", "file"]
            },
            "app": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "fastapi": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False
            }
        }
    }
