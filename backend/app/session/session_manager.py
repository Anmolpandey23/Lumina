"""
Session management for tracking browsing sessions and multi-page context
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BrowsingSession:
    """Represents a user browsing session"""
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    pages: List[Dict] = field(default_factory=list)
    queries: List[Dict] = field(default_factory=list)
    total_tokens_used: int = 0

    def add_page(self, page_url: str, page_content: str) -> None:
        """Record a page visit"""
        # Check if page already in session
        existing = next(
            (p for p in self.pages if p["url"] == page_url),
            None
        )

        if not existing:
            self.pages.append({
                "url": page_url,
                "title": self._extract_title(page_content),
                "visited_at": datetime.utcnow().isoformat(),
                "content_length": len(page_content)
            })
            logger.info(f"Added page to session {self.session_id}: {page_url}")

    def add_query(self, query: str, answer: str, tokens_used: int = 0) -> None:
        """Record a query and answer"""
        self.queries.append({
            "query": query,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat(),
            "tokens_used": tokens_used
        })
        self.total_tokens_used += tokens_used

    def get_context_summary(self) -> str:
        """Get summary of session context"""
        pages_info = [p["title"] or p["url"] for p in self.pages]
        return f"Session has visited: {', '.join(pages_info)}"

    def _extract_title(self, content: str) -> str:
        """Extract page title from content"""
        import re
        match = re.search(r'Page Title:\s*(.+?)(?:\n|$)', content)
        if match:
            return match.group(1).strip()
        return "Untitled"


class SessionManager:
    """Manages user browsing sessions"""

    def __init__(self):
        self.sessions: Dict[str, BrowsingSession] = {}

    def get_or_create_session(self, session_id: str) -> BrowsingSession:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = BrowsingSession(session_id=session_id)
            logger.info(f"Created new session: {session_id}")
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[BrowsingSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def save_session(self, session_id: str) -> None:
        """
        Save session to persistent storage
        In production, would save to database
        """
        session = self.sessions.get(session_id)
        if session:
            logger.info(f"Saving session {session_id} to storage")
            # TODO: Implement database persistence

    def get_active_sessions_count(self) -> int:
        """Get number of active sessions"""
        return len(self.sessions)

    def get_total_queries(self) -> int:
        """Get total queries across all sessions"""
        return sum(len(session.queries) for session in self.sessions.values())

    def get_multi_page_context(self, session_id: str) -> str:
        """
        Get combined context from all pages visited in session
        Useful for multi-page queries like "Compare page 1 with page 2"
        """
        session = self.get_session(session_id)
        if not session:
            return ""

        return f"\n---\n".join([
            p["url"] for p in session.pages
        ])

    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """Remove sessions older than specified hours"""
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        to_delete = [
            session_id for session_id, session in self.sessions.items()
            if session.created_at < cutoff_time
        ]

        for session_id in to_delete:
            self.delete_session(session_id)

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old sessions")

        return len(to_delete)
