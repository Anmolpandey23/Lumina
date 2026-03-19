"""
Chat endpoint routes
Main API endpoint for the extension to communicate with
"""

import os
import logging
import re
from difflib import SequenceMatcher
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional

from app.models.request_models import ChatRequest
from app.security.auth import validate_api_key
from app.security.input_validation import validate_input, check_sensitive_content
from app.utils.llm_client import LLMClient
from app.utils.text_correction import correct_query
from app.rag import RAGPipeline
from app.session.session_manager import SessionManager, BrowsingSession

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize components (would be better in app startup)
rag_pipeline = RAGPipeline()
session_manager = SessionManager()
session_video_context: dict[str, dict[str, str]] = {}


def _build_recent_history(session, max_turns: int = 4) -> str:
    """Build a compact recent conversation history block for the LLM."""
    recent_queries = session.queries[-max_turns:] if session and session.queries else []
    if not recent_queries:
        return ""

    history_lines = []
    for item in recent_queries:
        query_text = (item.get("query") or "").strip()
        if query_text:
            history_lines.append(f"User: {query_text}")

    return "\n".join(history_lines)


def _is_followup_query(query: str) -> bool:
    """Detect if query depends on prior conversation context."""
    q = (query or "").lower()
    followup_markers = [
        "what did i ask",
        "what i asked",
        "earlier",
        "before",
        "previous",
        "last question",
        "summarize",
        "what we talked",
        "as i said",
        "remember"
    ]
    return any(marker in q for marker in followup_markers)


def _is_notification_count_query(query: str) -> bool:
    """Detect explicit asks for notification count."""
    q = (query or "").lower()
    if "notification" not in q:
        return False
    return any(token in q for token in ["how many", "count", "number", "kitne", "kitni"])


def _extract_notification_count(page_content: str) -> Optional[int]:
    """Extract notification count from canonical UI lines in page content."""
    import re

    text = page_content or ""

    # 1) Prefer canonical extractor output (most reliable)
    canonical = re.search(r"YouTube notification count detected:\s*(\d+)", text, flags=re.IGNORECASE)
    if canonical:
        try:
            return int(canonical.group(1))
        except ValueError:
            pass

    # 2) Fallback to explicit icon line
    icon_line = re.search(r"Notification icon visible with count:\s*(\d+)", text, flags=re.IGNORECASE)
    if icon_line:
        try:
            return int(icon_line.group(1))
        except ValueError:
            pass

    # 3) Fallback: parse compact numeric token from scoped container text only.
    scoped = re.search(r"Notification container text:\s*(.+)", text, flags=re.IGNORECASE)
    if scoped:
        scoped_text = scoped.group(1)
        compact_tokens = re.findall(r"\b(\d{1,3})\+?\b", scoped_text)
        if compact_tokens:
            try:
                return max(int(token) for token in compact_tokens)
            except ValueError:
                pass

    return None


def _extract_subscription_items(page_content: str) -> list[str]:
    import re
    text = page_content or ""
    block_match = re.search(r"YOUTUBE SUBSCRIPTIONS:\n(.*?)(?:\n\n[A-Z][A-Z ]+:|\Z)", text, flags=re.DOTALL)
    if not block_match:
        return []
    block = block_match.group(1)
    items = re.findall(r"item\d+=(.+)", block)
    return [item.strip() for item in items if item.strip()]


def _is_subscription_query(query: str) -> bool:
    q = (query or "").lower()
    return "subscription" in q or "subsrib" in q or "subscribtion" in q


def _is_subscription_count_query(query: str) -> bool:
    q = (query or "").lower()
    return _is_subscription_query(q) and any(k in q for k in ["how many", "count", "number", "kitne", "kitni"])


def _is_first_subscription_query(query: str) -> bool:
    q = (query or "").lower()
    return _is_subscription_query(q) and any(k in q for k in ["first", "top", "extreme left", "left side"])


def _extract_youtube_cards(page_content: str) -> list[dict]:
    cards = []
    text = page_content or ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "CARD|" not in line:
            continue

        # Handle lines where CARD payload is prefixed by bullets/spaces/labels.
        card_payload = line[line.find("CARD|"):]
        parts = card_payload.split("|")
        card = {}
        for part in parts[1:]:
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            card[k.strip()] = v.strip()
        if card.get("title"):
            cards.append(card)

    # Fallback block parse if CARD lines were collapsed into one chunk.
    if not cards:
        block_match = re.search(r"YOUTUBE VIDEO CARDS:\n(.*?)(?:\n\n[A-Z][A-Z ]+:|\Z)", text, flags=re.DOTALL)
        if block_match:
            block = block_match.group(1)
            for chunk in re.findall(r"CARD\|[^\n]+", block):
                parts = chunk.split("|")
                card = {}
                for part in parts[1:]:
                    if "=" not in part:
                        continue
                    k, v = part.split("=", 1)
                    card[k.strip()] = v.strip()
                if card.get("title"):
                    cards.append(card)

    return cards


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())).strip()


def _significant_tokens(value: str) -> set[str]:
    stopwords = {
        "the", "a", "an", "is", "are", "of", "to", "in", "on", "for", "with", "and", "or",
        "what", "which", "name", "its", "it", "this", "that", "can", "you", "see", "song", "video",
        "duration", "length", "long", "runtime", "size", "minute", "minutes", "second", "seconds"
    }
    tokens = [token for token in _normalize_text(value).split() if len(token) > 2 and token not in stopwords]
    return set(tokens)


def _find_best_card_from_query(query: str, cards: list[dict]) -> Optional[dict]:
    if not query or not cards:
        return None

    query_norm = _normalize_text(query)
    query_tokens = _significant_tokens(query)
    best_card = None
    best_score = 0.0

    for card in cards:
        title = card.get("title", "")
        if not title:
            continue

        title_norm = _normalize_text(title)
        title_tokens = _significant_tokens(title)
        if not title_tokens:
            continue

        overlap = len(query_tokens & title_tokens)
        fuzzy_overlap = 0
        for qt in query_tokens:
            if qt in title_tokens:
                fuzzy_overlap += 1
                continue
            # Allow slight spelling variants (e.g., awara vs aawaara).
            if any(SequenceMatcher(None, qt, tt).ratio() >= 0.82 for tt in title_tokens):
                fuzzy_overlap += 1

        title_coverage = max(overlap, fuzzy_overlap) / max(1, len(title_tokens))
        query_coverage = max(overlap, fuzzy_overlap) / max(1, len(query_tokens))
        contains_score = 0.0
        if title_norm and title_norm in query_norm:
            contains_score = 1.0
        elif query_norm and len(query_norm) >= 10 and query_norm in title_norm:
            contains_score = 0.8

        score = max(title_coverage, query_coverage, contains_score)
        if score > best_score:
            best_score = score
            best_card = card

    threshold = 0.35 if len(query_tokens) <= 1 else 0.5
    return best_card if best_score >= threshold else None


def _remember_from_query_if_possible(session_id: str, query: str, cards: list[dict]) -> None:
    # Persist the card most likely referenced by the user so pronoun follow-ups resolve correctly.
    match = _find_best_card_from_query(query, cards)
    if not match:
        return

    title = match.get("title", "")
    channel = match.get("channel", "")
    if title or channel:
        _remember_video_context(session_id, title, channel)


def _is_video_lessons_query(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in [
        "how many videos", "how many lessons", "how many lectures",
        "number of videos", "number of lessons", "number of lectures",
        "total videos", "total lessons"
    ])


def _extract_target_video_title(query: str, previous_queries: Optional[list] = None, cards: Optional[list] = None) -> str:
    """Generic video title resolver: tries current query against cards, then session history."""
    if cards:
        match = _find_best_card_from_query(query, cards)
        if match and match.get("title"):
            return match["title"].lower()
    if previous_queries and cards:
        return _infer_target_from_recent_queries(previous_queries, cards)
    return ""


def _infer_target_from_recent_queries(previous_queries: Optional[list], cards: list[dict]) -> str:
    if not previous_queries or not cards:
        return ""

    for item in reversed(previous_queries[-8:]):
        prior_query = (item.get("query") or "").strip()
        if not prior_query:
            continue
        match = _find_best_card_from_query(prior_query, cards)
        if match and match.get("title"):
            return match["title"].lower()
    return ""


def _remember_video_context(session_id: str, title: str, channel: str) -> None:
    session_video_context[session_id] = {
        "title": title or "",
        "channel": channel or ""
    }


def _recall_video_context(session_id: str) -> dict[str, str]:
    return session_video_context.get(session_id, {})


def _is_video_channel_query(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in ["channel", "chanel", "chnnel", "name of its channel", "name if the channel"])


def _is_video_duration_query(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in [
        "duration", "length", "long", "runtime", "how long", "size of the video", "video size", "kitne minute"
    ])


def _normalize_duration(raw: str) -> str:
    """Normalize duration text from cards to a compact hh:mm:ss/mm:ss format."""
    value = (raw or "").strip()
    if not value:
        return ""

    value = re.sub(r"\s+", "", value)

    # Already in mm:ss or hh:mm:ss form.
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", value):
        return value

    # Fallback from text variants like "13 min 16 sec".
    h_match = re.search(r"(\d+)\s*h", value, flags=re.IGNORECASE)
    m_match = re.search(r"(\d+)\s*m", value, flags=re.IGNORECASE)
    s_match = re.search(r"(\d+)\s*s", value, flags=re.IGNORECASE)
    if h_match or m_match or s_match:
        h = int(h_match.group(1)) if h_match else 0
        m = int(m_match.group(1)) if m_match else 0
        s = int(s_match.group(1)) if s_match else 0
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    return raw.strip()


def _is_youtube_page(page_url: str, page_content: str) -> bool:
    url = (page_url or "").lower()
    content = page_content or ""
    if "youtube.com" in url or "youtu.be" in url:
        return True
    # Backup signal when URL is hidden/obfuscated but extractor emits YouTube card payload.
    return "YOUTUBE VIDEO CARDS:" in content and "CARD|" in content


def _default_model_for_provider(provider: str) -> str:
    if provider == "gemini":
        return "gemini-pro-latest"
    if provider == "huggingface":
        return "meta-llama/Llama-3.1-8B-Instruct"
    if provider == "ollama":
        return "mistral"
    return "gpt-3.5-turbo"


def _build_llm_client(request: ChatRequest) -> LLMClient:
    """Create LLM client using request overrides, falling back to backend defaults."""
    provider = (request.llm_provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    env_model = os.getenv("LLM_MODEL")
    model = (request.llm_model or env_model or _default_model_for_provider(provider)).strip()
    api_key = (request.llm_api_key or "").strip() or None

    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key

    return LLMClient(provider_type=provider, model=model, **kwargs)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Main chat endpoint
    Processes user query against page content and returns RAG-grounded answer
    """
    
    # Validate API key if required
    validate_api_key(authorization)

    try:
        # Validate input
        input_data = {
            "query": request.query,
            "page_content": request.page_content,
            "page_url": request.page_url,
            "session_id": request.session_id
        }
        input_data = validate_input(input_data)

        # Check for sensitive content
        if check_sensitive_content(request.page_content):
            logger.warning(f"Sensitive content detected in {request.page_url}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Page contains sensitive information. Content extraction disabled."
                }
            )

        # In private mode, keep all context ephemeral for this request only.
        if request.private_mode:
            session = BrowsingSession(session_id=request.session_id)
        else:
            session = session_manager.get_or_create_session(request.session_id)
            session.add_page(request.page_url, request.page_content)

        def _deterministic_response(answer: str, confidence: float = 1.0, tokens_used: int = 1):
            response = {
                "success": True,
                "answer": answer,
                "confidence": confidence,
                "tokens_used": tokens_used,
                "sources": [],
                "session_id": request.session_id
            }
            session.add_query(request.query, answer, tokens_used)
            if not request.private_mode:
                session_manager.save_session(request.session_id)
            return response

        is_youtube = _is_youtube_page(request.page_url, request.page_content)

        # Deterministic shortcut: notification count questions should use parsed UI signals.
        if is_youtube and _is_notification_count_query(request.query):
            notif_count = _extract_notification_count(request.page_content)
            if notif_count is not None:
                return _deterministic_response(str(notif_count), confidence=1.0, tokens_used=1)
            return _deterministic_response(
                "I could not read the exact notification count from the extracted page data yet. Please reload the Lumina extension and refresh the YouTube tab, then ask again.",
                confidence=0.0,
                tokens_used=0
            )

        # Deterministic shortcut: YouTube subscriptions count.
        if is_youtube and _is_subscription_count_query(request.query):
            subs = _extract_subscription_items(request.page_content)
            if subs:
                return _deterministic_response(str(len(subs)), confidence=1.0, tokens_used=1)

        # Deterministic shortcut: first subscription name.
        if is_youtube and _is_first_subscription_query(request.query):
            subs = _extract_subscription_items(request.page_content)
            if subs:
                return _deterministic_response(subs[0], confidence=1.0, tokens_used=max(1, len(subs[0].split())))

        # Deterministic shortcut: video lessons/videos count for a named card.
        if is_youtube and _is_video_lessons_query(request.query):
            cards = _extract_youtube_cards(request.page_content)
            if cards:
                match = _find_best_card_from_query(request.query, cards)
                if not match:
                    inferred = _infer_target_from_recent_queries(session.queries[-8:], cards)
                    if inferred:
                        match = next((c for c in cards if inferred in c.get("title", "").lower()), None)
                lessons = (match or {}).get("lessons")
                channel = (match or {}).get("channel", "")
                if lessons:
                    if not request.private_mode:
                        _remember_video_context(request.session_id, (match or {}).get("title", ""), channel)
                    return _deterministic_response(str(lessons), confidence=1.0, tokens_used=1)

        cards = _extract_youtube_cards(request.page_content) if is_youtube else []
        if is_youtube and cards and not _is_video_channel_query(request.query) and not request.private_mode:
            _remember_from_query_if_possible(request.session_id, request.query, cards)

        # Deterministic shortcut: channel name for a named/previously referenced card.
        if is_youtube and _is_video_channel_query(request.query):
            # Direct title mention in current query should win.
            direct_match = _find_best_card_from_query(request.query, cards)
            target = direct_match["title"].lower() if (direct_match and direct_match.get("title")) else ""

            # Infer from recent non-pronoun query if current question is only a follow-up.
            if not target:
                target = _infer_target_from_recent_queries(session.queries, cards)

            # Fallback to the last deterministic video context in this session.
            if not target and not request.private_mode:
                remembered = _recall_video_context(request.session_id)
                if remembered.get("title"):
                    target = remembered["title"].lower()

            if cards and target:
                match = next((c for c in cards if target in c.get("title", "").lower()), None)
                channel = (match or {}).get("channel")
                if channel:
                    if not request.private_mode:
                        _remember_video_context(request.session_id, (match or {}).get("title", target), channel)
                    return _deterministic_response(channel, confidence=1.0, tokens_used=max(1, len(channel.split())))

            if not request.private_mode:
                remembered = _recall_video_context(request.session_id)
                if remembered.get("channel"):
                    return _deterministic_response(
                        remembered["channel"],
                        confidence=1.0,
                        tokens_used=max(1, len(remembered["channel"].split()))
                    )

        # Deterministic shortcut: exact video duration from YouTube cards.
        if is_youtube and _is_video_duration_query(request.query):
            duration_match = _find_best_card_from_query(request.query, cards)
            if not duration_match:
                inferred = _infer_target_from_recent_queries(session.queries[-8:], cards)
                if inferred:
                    duration_match = next((c for c in cards if inferred in c.get("title", "").lower()), None)

            duration = _normalize_duration((duration_match or {}).get("duration", ""))
            if duration:
                return _deterministic_response(duration, confidence=1.0, tokens_used=1)

        # Correct spelling mistakes only for retrieval (keep original user wording for answer generation)
        corrected_query, was_corrected = correct_query(request.query, cutoff=0.75)
        retrieval_query = corrected_query if was_corrected else request.query
        if was_corrected:
            logger.info(f"Retrieval query corrected: '{request.query}' → '{corrected_query}'")

        # Process page through RAG pipeline
        processing_result = rag_pipeline.process_page(
            request.page_content,
            request.page_url
        )

        if not processing_result["success"]:
            logger.error(f"RAG processing failed: {processing_result}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Failed to process page content"
                }
            )

        # Retrieve relevant context (using corrected query only for better matching)
        retrieved_chunks = rag_pipeline.retrieve_context(
            retrieval_query,
            page_url=request.page_url,
            top_k=5
        )

        if not retrieved_chunks:
            # Fallback: try to extract relevant sentences manually
            logger.warning("No chunks retrieved, using fallback")
            context = request.page_content[:1000]  # Use first 1000 chars
        else:
            context = rag_pipeline.build_context_prompt(retrieved_chunks)

        # Add recent in-session conversation memory for follow-up questions
        recent_history = _build_recent_history(session)
        if recent_history and _is_followup_query(request.query):
            context = (
                f"{context}\n\n"
                "RECENT CONVERSATION HISTORY:\n"
                f"{recent_history}\n\n"
                "Use this history only to resolve explicit follow-up questions. "
                "For normal page questions, ignore history and answer from page context."
            )

        # Generate answer using LLM
        generation_result = _build_llm_client(request).generate_answer(
            query=request.query,
            context=context,
            max_tokens=request.max_tokens,
            temperature=0.7
        )

        # Calculate confidence score based on retrieval
        confidence = (
            sum(chunk["score"] for chunk in retrieved_chunks) / len(retrieved_chunks)
            if retrieved_chunks else 0.3
        )

        # Prepare response
        response = {
            "success": generation_result["success"],
            "answer": generation_result["answer"],
            "confidence": confidence,
            "tokens_used": generation_result.get("tokens_used", 0),
            "sources": [
                {
                    "id": chunk["id"],
                    "score": chunk["score"],
                    "page_url": chunk.get("metadata", {}).get("page_url"),
                    "text_snippet": chunk.get("text", "")[:500]
                }
                for chunk in retrieved_chunks
            ] if retrieved_chunks else [],
            "session_id": request.session_id
        }

        # Update session
        session.add_query(request.query, response["answer"])

        # Store to DB if not in private mode
        if not request.private_mode:
            session_manager.save_session(request.session_id)

        logger.info(f"Chat request processed - session: {request.session_id}, confidence: {confidence:.2f}")
        
        return response

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session information and history"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "pages_visited": len(session.pages),
            "pages": [p["url"] for p in session.pages],
            "total_queries": len(session.queries),
            "created_at": session.created_at.isoformat(),
            "queries": session.queries[-20:]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving session")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear session data"""
    try:
        session_manager.delete_session(session_id)
        rag_pipeline.retriever.clear_page(session_id)
        # Remove video context memory to prevent unbounded growth
        session_video_context.pop(session_id, None)
        return {"success": True, "message": f"Session {session_id} cleared"}
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail="Error clearing session")


@router.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        return {
            "rag_pipeline": rag_pipeline.get_stats(),
            "active_sessions": session_manager.get_active_sessions_count(),
            "total_queries": session_manager.get_total_queries()
        }
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving stats")
