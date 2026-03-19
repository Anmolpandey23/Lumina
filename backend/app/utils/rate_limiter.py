"""
Rate limiting utilities
"""

import logging
from typing import Dict
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter based on session/user ID"""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.rpm_limit = requests_per_minute
        self.rph_limit = requests_per_hour
        
        self.minute_requests: Dict[str, list] = defaultdict(list)
        self.hour_requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, session_id: str) -> bool:
        """Check if request is allowed for session"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        self.minute_requests[session_id] = [
            ts for ts in self.minute_requests[session_id]
            if ts > minute_ago
        ]
        self.hour_requests[session_id] = [
            ts for ts in self.hour_requests[session_id]
            if ts > hour_ago
        ]

        # Check limits
        if len(self.minute_requests[session_id]) >= self.rpm_limit:
            logger.warning(f"Rate limit (per minute) exceeded for {session_id}")
            return False

        if len(self.hour_requests[session_id]) >= self.rph_limit:
            logger.warning(f"Rate limit (per hour) exceeded for {session_id}")
            return False

        # Record request
        self.minute_requests[session_id].append(now)
        self.hour_requests[session_id].append(now)

        return True

    def get_remaining(self, session_id: str) -> Dict[str, int]:
        """Get remaining requests for session"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        minute_count = len([
            ts for ts in self.minute_requests[session_id]
            if ts > minute_ago
        ])
        hour_count = len([
            ts for ts in self.hour_requests[session_id]
            if ts > hour_ago
        ])

        return {
            "remaining_per_minute": max(0, self.rpm_limit - minute_count),
            "remaining_per_hour": max(0, self.rph_limit - hour_count)
        }
