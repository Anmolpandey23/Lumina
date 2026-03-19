"""
Input validation and sanitization
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def validate_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize input data
    
    Args:
        data: Input data dictionary
        
    Returns:
        Validated data
        
    Raises:
        ValueError if invalid
    """
    # Validate query
    if "query" in data:
        query = data["query"].strip()
        if not query:
            raise ValueError("Query cannot be empty")
        if len(query) > 5000:
            raise ValueError("Query exceeds maximum length")
        data["query"] = sanitize_string(query)

    # Validate page content
    if "page_content" in data:
        content = data["page_content"].strip()
        if not content:
            raise ValueError("Page content cannot be empty")
        if len(content) > 100000:
            raise ValueError("Page content exceeds maximum length")
        data["page_content"] = sanitize_string(content)

    # Validate URL
    if "page_url" in data:
        url = data["page_url"].strip()
        if not is_valid_url(url):
            raise ValueError("Invalid page URL")
        data["page_url"] = url

    # Validate session ID
    if "session_id" in data:
        session_id = data["session_id"].strip()
        if not session_id or len(session_id) > 100:
            raise ValueError("Invalid session ID")
        data["session_id"] = session_id

    return data


def sanitize_string(text: str) -> str:
    """Remove potentially harmful content"""
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))


def check_sensitive_content(text: str) -> bool:
    """Check for potentially sensitive content"""
    sensitive_patterns = [
        r'password\s*:\s*',
        r'credit\s*card',
        r'ssn\s*:\s*',
        r'api[_-]?key\s*:\s*',
        r'secret\s*:\s*'
    ]
    
    text_lower = text.lower()
    for pattern in sensitive_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False
