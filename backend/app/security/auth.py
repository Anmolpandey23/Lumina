"""
Security and authentication utilities
"""

import os
import logging
from fastapi import HTTPException, Header
from typing import Optional

logger = logging.getLogger(__name__)


def validate_api_key(authorization: Optional[str] = Header(None)) -> str:
    """
    Validate API key from request header
    
    Args:
        authorization: Authorization header
        
    Returns:
        API key if valid
        
    Raises:
        HTTPException if invalid
    """
    # API key validation is optional by default
    # Set REQUIRE_API_KEY=true to enforce
    
    if not os.getenv("REQUIRE_API_KEY", "false").lower() == "true":
        return "public"

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Extract bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    valid_keys = os.getenv("VALID_API_KEYS", "").split(",")

    if token not in valid_keys:
        logger.warning("Invalid API key attempt detected.")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return token
