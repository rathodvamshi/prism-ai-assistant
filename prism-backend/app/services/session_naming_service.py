import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.db.mongo_client import sessions_collection
from app.db.redis_client import redis_client
from app.utils.llm_client import (
    build_session_metadata,
    generate_session_title,
    should_generate_session_title,
)

logger = logging.getLogger(__name__)

SESSION_TITLE_LOCK_TTL_SECONDS = 120


def _compose_title_context(
    user_message: str,
    assistant_response: str = "",
    intent: Optional[str] = None,
    entities: Optional[Any] = None,
) -> str:
    parts = [f"User: {user_message.strip()}"]
    if assistant_response:
        parts.append(f"Assistant: {assistant_response.strip()}")
    if intent:
        parts.append(f"Intent: {intent}")
    if entities:
        try:
            entity_text = entities if isinstance(entities, str) else json.dumps(entities, default=str)
        except Exception:
            entity_text = str(entities)
        parts.append(f"Entities: {entity_text}")
    return "\n".join(part for part in parts if part)


async def generate_and_persist_session_title(
    session: Dict[str, Any],
    user_message: str,
    assistant_response: str,
    chat_id: str,
    intent: Optional[str] = None,
    entities: Optional[Any] = None,
    allow_rename: bool = False,
) -> Optional[Dict[str, Any]]:
    """Generate a single session title from the first meaningful turn and persist it once."""
    current_title = session.get("title") or session.get("sessionTitle") or ""
    message_count = len(session.get("messages", []))
    title_already_generated = session.get("titleGenerated") is True

    if not assistant_response.strip():
        return None

    if not allow_rename and not should_generate_session_title(
        user_message,
        current_title=current_title,
        message_count=message_count,
        title_already_generated=title_already_generated,
    ):
        return None

    if allow_rename and not should_generate_session_title(
        user_message,
        current_title=current_title,
        message_count=message_count,
        title_already_generated=title_already_generated,
    ):
        return None

    context_text = _compose_title_context(
        user_message,
        assistant_response,
        intent=intent,
        entities=entities,
    )
    context_hash = hashlib.sha1(context_text.lower().encode("utf-8")).hexdigest()
    lock_key = f"session:title:lock:{chat_id}:{context_hash}"

    try:
        acquired = await redis_client.set(lock_key, "1", ex=SESSION_TITLE_LOCK_TTL_SECONDS, nx=True)
        if not acquired:
            return None
    except Exception as cache_error:
        logger.debug(f"Session title lock skipped: {cache_error}")

    title = await generate_session_title(
        user_message,
        assistant_response=assistant_response,
        session_id=chat_id,
        current_title=current_title,
        message_count=message_count,
        intent=intent,
        entities=entities,
        title_already_generated=title_already_generated,
    )

    if not title:
        return None

    metadata = build_session_metadata(context_text, title)
    title_confidence = 0.88
    if assistant_response.strip():
        title_confidence += 0.04
    if intent:
        title_confidence += 0.03
    if entities:
        title_confidence += 0.03
    title_confidence = round(min(title_confidence, 0.98), 2)

    update_time = datetime.utcnow()
    update_filter: Dict[str, Any] = {"_id": session["_id"]}
    if not allow_rename:
        update_filter["$or"] = [
            {"titleGenerated": {"$ne": True}},
            {"title": {"$in": [None, "", "New Chat", "Untitled", "New Conversation", "New Beginning", "New Idea"]}},
            {"sessionTitle": {"$in": [None, "", "New Chat", "Untitled", "New Conversation", "New Beginning", "New Idea"]}},
        ]

    result = await sessions_collection.update_one(
        update_filter,
        {
            "$set": {
                "title": title,
                "sessionTitle": title,
                "sessionSummary": metadata["sessionSummary"],
                "primaryTopic": metadata["primaryTopic"],
                "tags": metadata["tags"],
                "titleGenerated": True,
                "titleConfidence": title_confidence,
                "titleGeneratedAt": update_time,
                "lastMessageAt": update_time,
                "updated_at": update_time,
                "updatedAt": update_time,
            }
        },
    )

    if result.modified_count == 0 and not allow_rename:
        return None

    return {
        "sessionId": chat_id,
        "title": title,
        "sessionTitle": title,
        "sessionSummary": metadata["sessionSummary"],
        "primaryTopic": metadata["primaryTopic"],
        "tags": metadata["tags"],
        "titleGenerated": True,
        "titleConfidence": title_confidence,
    }
