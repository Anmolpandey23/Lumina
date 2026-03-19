"""
Health check and status endpoints
"""

from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns service status and readiness
    """
    try:
        return {
            "status": "healthy",
            "service": "ai-browsing-copilot",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/ready")
async def readiness_check():
    """
    Readiness probe for Kubernetes/Docker
    Checks if service is ready to accept requests
    """
    try:
        # In production, check database connections, etc.
        return {
            "ready": True,
            "service": "ai-browsing-copilot"
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Not ready")
