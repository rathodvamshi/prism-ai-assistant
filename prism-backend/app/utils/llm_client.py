from groq import AsyncGroq # <--- MUST be AsyncGroq
from app.config import settings
from app.db.redis_client import redis_client
import json
import logging
import asyncio  # 🚀 Required for event loop flush
from typing import Any, Optional, List
import hashlib
import re

logger = logging.getLogger(__name__)

_default_client: Optional[AsyncGroq] = None


def _get_default_client() -> AsyncGroq:
    global _default_client
    if _default_client is None:
        _default_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _default_client


# Helper to return the LLM client (for sync/legacy code)
def get_llm_client():
    return _get_default_client()

# 🎚️ Import Adaptive Quality Service
try:
    from app.services.adaptive_quality import (
        adaptive_quality,
        get_adaptive_model_params,
        record_generation_start,
        record_generation_metrics
    )
    ADAPTIVE_QUALITY_ENABLED = True
except ImportError:
    ADAPTIVE_QUALITY_ENABLED = False
    logger.warning("⚠️ Adaptive Quality Service not available")

def get_client_for_key(api_key: str | None = None) -> AsyncGroq:
    """Get AsyncGroq client - uses provided key or falls back to platform key."""
    if api_key and api_key != settings.GROQ_API_KEY:
        return AsyncGroq(api_key=api_key)
    return _get_default_client()


SESSION_TITLE_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
SESSION_TITLE_PLACEHOLDERS = {
    "",
    "new chat",
    "untitled",
    "new conversation",
    "conversation",
    "session 1",
    "shared conversation",
    "new beginning",
    "new idea",
}
SESSION_TITLE_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "what's up",
    "whats up",
    "yo",
    "sup",
}
SESSION_TITLE_STOPWORDS = {
    "a", "an", "and", "are", "around", "as", "at", "be", "build", "can",
    "could", "do", "for", "from", "give", "help", "i", "in", "into", "is",
    "it", "learn", "let", "like", "me", "my", "need", "of", "on", "or",
    "please", "prepare", "show", "teach", "the", "to", "want", "we", "with",
    "would", "you", "your", "wanting", "using", "about", "want", "wanting",
    "want", "make", "build", "create", "design", "understand", "explain",
    "want", "want to", "prepare", "prep", "interview", "question", "questions",
}
TITLE_KEYWORD_MAP = {
    "backend": "Backend",
    "frontend": "Frontend",
    "api": "API",
    "apis": "API",
    "database": "Database",
    "dbms": "DBMS",
    "ai": "AI",
    "ml": "ML",
    "react": "React",
    "hooks": "Hooks",
    "architecture": "Architecture",
    "interview": "Interview",
    "prep": "Prep",
    "preparation": "Prep",
    "development": "Development",
    "coding": "Coding",
    "learning": "Learning",
    "system": "System",
    "memory": "Memory",
    "java": "Java",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "node": "Node",
    "nodejs": "Node.js",
}


def _normalize_title_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\"'`]+", "", str(text)).strip()
    cleaned = re.sub(r"[\s\-_/]+", " ", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9\.\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _smart_title_case(words: List[str]) -> str:
    rendered = []
    for word in words:
        if not word:
            continue
        key = word.lower().strip(".")
        if key in TITLE_KEYWORD_MAP:
            rendered.append(TITLE_KEYWORD_MAP[key])
            continue
        if word.isupper() and len(word) <= 6:
            rendered.append(word)
            continue
        if re.fullmatch(r"[A-Za-z]+\.[A-Za-z]+", word):
            rendered.append(word)
            continue
        rendered.append(word[:1].upper() + word[1:].lower())
    return " ".join(rendered).strip()


def _tokenize_title_keywords(message: str) -> List[str]:
    normalized = _normalize_title_text(message).lower()
    if not normalized:
        return []
    tokens = re.findall(r"[A-Za-z0-9\.]+", normalized)
    keywords: List[str] = []
    for token in tokens:
        key = token.lower().strip(".")
        if not key or key in SESSION_TITLE_STOPWORDS:
            continue
        if key in TITLE_KEYWORD_MAP:
            mapped = TITLE_KEYWORD_MAP[key]
        elif len(key) <= 2 and not key.isalpha():
            continue
        else:
            mapped = key
        if mapped not in keywords:
            keywords.append(mapped)
    return keywords


def _looks_like_greeting_only(message: str) -> bool:
    normalized = _normalize_title_text(message).lower()
    if not normalized:
        return True
    if normalized in SESSION_TITLE_GREETINGS:
        return True
    tokens = _tokenize_title_keywords(normalized)
    if not tokens:
        return True
    if len(tokens) == 1 and tokens[0] in {"thanks", "thank", "ok", "okay", "cool", "sure"}:
        return True
    return False


def should_generate_session_title(
    message: str,
    current_title: Optional[str] = None,
    message_count: int = 0,
    *,
    title_already_generated: bool = False,
) -> bool:
    """
    Whether we should run auto title generation for this completion.

    Policy: at most one auto title per session — only when the session still has
    a placeholder title and we have not already marked titleGenerated.
    No automatic renames on later messages (removed old message_count>=6 overlap logic).
    """
    if title_already_generated:
        return False
    if _looks_like_greeting_only(message):
        return False

    current = _normalize_title_text(current_title or "").lower()
    if current in SESSION_TITLE_PLACEHOLDERS:
        return True

    return False


def _fallback_session_title(message: str) -> str:
    keywords = _tokenize_title_keywords(message)
    if not keywords:
        return "General Discussion"

    first_words = keywords[:4]
    title = _smart_title_case(first_words)
    if not title:
        return "General Discussion"

    # Light intent shaping for natural titles.
    lowered = message.lower()
    if any(word in lowered for word in ["teach me", "learn", "study", "explain"]):
        if len(first_words) < 4:
            title = f"{title} Learning" if title else "Learning"
    elif any(word in lowered for word in ["prep", "prepare", "preparation", "interview"]):
        if "Interview" not in title:
            if "Prep" in title:
                title = f"{title} Interview"
            elif len(first_words) < 4:
                title = f"{title} Interview Prep" if title else "Interview Prep"
    elif any(word in lowered for word in ["build", "design", "architect", "develop"]):
        if "Development" not in title and len(first_words) < 4:
            title = f"{title} Development"

    title_words = title.split()[:5]
    return " ".join(title_words) if title_words else "General Discussion"


def _truncate_title(title: str, max_words: int = 5) -> str:
    cleaned = _normalize_title_text(title)
    if not cleaned:
        return ""
    words = cleaned.split()
    if not words:
        return ""
    return _smart_title_case(words[:max_words])


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


def _is_placeholder_title(title: Optional[str]) -> bool:
    normalized = _normalize_title_text(title or "").lower()
    return normalized in SESSION_TITLE_PLACEHOLDERS


def build_session_metadata(message: str, title: Optional[str] = None) -> dict:
    keywords = _tokenize_title_keywords(message)
    title_keywords = _tokenize_title_keywords(title or "")
    combined = []
    for token in title_keywords + keywords:
        if token and token not in combined:
            combined.append(token)

    primary_topic = None
    if combined:
        primary_topic = _smart_title_case([combined[0]])
    elif title:
        primary_topic = _truncate_title(title, 1)

    tags = [token.lower() for token in combined[:5]]
    if not tags and title:
        tags = [word.lower() for word in _normalize_title_text(title).split()[:3]]

    summary_source = _smart_title_case(combined[:4]) if combined else _truncate_title(title or message, 4)
    if not summary_source:
        summary_source = "General Discussion"

    if len(summary_source.split()) <= 1 and title:
        summary_source = _truncate_title(title, 4)

    return {
        "sessionSummary": f"Discussion about {summary_source}",
        "primaryTopic": primary_topic or summary_source,
        "tags": tags,
    }


async def generate_session_title(
    user_message: str,
    assistant_response: str = "",
    session_id: Optional[str] = None,
    current_title: Optional[str] = None,
    message_count: int = 0,
    intent: Optional[str] = None,
    entities: Optional[Any] = None,
    *,
    title_already_generated: bool = False,
) -> Optional[str]:
    """
    Generate a clean session title from the first meaningful user message.
    Returns None if the message is too generic or the session should keep its title.
    """
    if not should_generate_session_title(
        user_message,
        current_title=current_title,
        message_count=message_count,
        title_already_generated=title_already_generated,
    ):
        return None

    combined_context = _compose_title_context(user_message, assistant_response, intent=intent, entities=entities)
    normalized_message = _normalize_title_text(combined_context)
    cache_key = None
    if session_id:
        message_hash = hashlib.sha1(normalized_message.lower().encode("utf-8")).hexdigest()
        cache_key = f"session:title:{session_id}:{message_hash}"
        try:
            cached_title = await redis_client.get(cache_key)
            if cached_title:
                cached_title = _truncate_title(cached_title, 5)
                if cached_title and (_is_placeholder_title(current_title) or cached_title == current_title):
                    return cached_title
        except Exception as cache_error:
            logger.debug(f"Session title cache read skipped: {cache_error}")

    candidate = None
    try:
        system_prompt = (
            "You write premium chat session titles.\n"
            "Create a concise, human-sounding title from the first meaningful user turn and the assistant's first response.\n"
            "Rules:\n"
            "- 2 to 5 words only\n"
            "- No emojis\n"
            "- No quotes\n"
            "- No punctuation spam\n"
            "- No generic names like New Chat, Conversation, Session 1\n"
            "- Use the main topic plus the user's intent\n"
            "- Keep proper capitalization\n"
            "- Preserve acronyms like AI, DBMS, API, React\n"
            "Return only the title text."
        )

        completion = await _get_default_client().chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_context},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,
            max_tokens=16,
        )

        candidate = completion.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Session title generation failed: {e}")

    title = _truncate_title(candidate or "", 5)
    if not title or _normalize_title_text(title).lower() in SESSION_TITLE_PLACEHOLDERS:
        title = _fallback_session_title(user_message)

    title = _truncate_title(title, 5)
    if not title:
        title = "General Discussion"

    # Keep titles meaningful and concise.
    if title.lower() in SESSION_TITLE_PLACEHOLDERS:
        title = "General Discussion"

    if current_title and not _is_placeholder_title(current_title):
        if message_count >= 6:
            current_keywords = set(_tokenize_title_keywords(current_title))
            new_keywords = set(_tokenize_title_keywords(title))
            overlap = len(current_keywords & new_keywords) / max(len(current_keywords | new_keywords), 1)
            if overlap >= 0.35:
                return None
        else:
            return None

    if cache_key:
        try:
            await redis_client.setex(cache_key, SESSION_TITLE_CACHE_TTL_SECONDS, title)
        except Exception as cache_error:
            logger.debug(f"Session title cache write skipped: {cache_error}")

    return title


async def get_llm_response(
    prompt: str, 
    system_prompt: str = "You are a helpful AI assistant.", 
    image_url: str | None = None,
    timeout: float = 30.0,
    model: str = "llama-3.3-70b-versatile"
) -> str:
    """
    Sends a prompt to Groq. Supports text-only and vision via image_url.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt (defaults to basic assistant)
        image_url: Optional image URL for vision models
        timeout: Request timeout in seconds (default 30s)
    
    Returns:
        AI response text
    """
    try:
        if image_url:
            model_name = "llama-3.2-11b-vision-preview"
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ]
        else:
            model_name = model
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

        import asyncio
        chat_completion = await asyncio.wait_for(
            _get_default_client().chat.completions.create(
                messages=messages,
                model=model_name,
                temperature=0.8,  # Creative and engaging
                max_tokens=2048,  # Detailed responses
                top_p=0.95,      # Focused but creative
                stop=None,
                stream=False,
            ),
            timeout=timeout
        )
        return chat_completion.choices[0].message.content
    except asyncio.TimeoutError:
        logger.warning(f"LLM Timeout: Request took longer than {timeout}s")
        return "I'm taking a bit longer to think... Let me get back to you! 🤔"
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "I'm having trouble processing right now. Let me try again! 😅"

async def get_llm_response_stream(
    prompt: str, 
    system_prompt: str, 
    image_url: str | None = None,
    model: str = "llama-3.3-70b-versatile", # Default to high-intelligence
    conversation_history: list | None = None,  # 🆕 Multi-turn conversation support
    api_key: str | None = None  # 🔑 User's API key (None = use platform key)
):
    """
    Streams response from Groq in real-time chunks.
    Yields small text chunks (5-20 characters) for smooth UI updates.
    
    Args:
        prompt: Current user message
        system_prompt: System prompt with identity/context
        image_url: Optional image for vision models
        model: Model to use
        conversation_history: Optional list of previous messages in format:
            [{"role": "user"|"assistant", "content": "..."}]
    """
    try:
        if image_url:
            model_name = "llama-3.2-11b-vision-preview"
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ]
        else:
            model_name = model
            # 🆕 BUILD MULTI-TURN MESSAGE ARRAY (ENHANCED)
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if provided (recent turns for context continuity)
            # 🚀 ULTRA-FAST: Simplified history handling
            if conversation_history and len(conversation_history) > 0:
                # Quick limit: max 4 messages, 500 chars each
                for msg in conversation_history[-4:]:
                    role = msg.get("role", "user").lower()
                    content = msg.get("content", "")[:500]  # Hard truncate
                    if role in ["user", "assistant"] and content:
                        messages.append({"role": role, "content": content})
            
            # Add current user message
            messages.append({"role": "user", "content": prompt})

        # 🚀 ULTRA-FAST TPM SAFEGUARD: Quick check, simple truncation
        if "llama-3.1-8b-instant" in model_name:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            
            # If over 18k chars (~4.5k tokens), truncate system prompt
            if total_chars > 18000:
                system_content = messages[0]["content"]
                # Keep first 8k chars of system prompt
                messages[0] = {"role": "system", "content": system_content[:8000]}
            
            dynamic_max_tokens = 600  # 🚀 Reduced for faster response
        else:
            # 70B model - can handle more output
            dynamic_max_tokens = 1200

        # 🚀 ULTRA-SPEED: Dynamic max_tokens based on query length
        prompt_words = len(prompt.split())
        if prompt_words < 10:
            dynamic_max_tokens = min(dynamic_max_tokens, 250)  # Short query = short response
        elif prompt_words < 25:
            dynamic_max_tokens = min(dynamic_max_tokens, 400)
        elif prompt_words < 50:
            dynamic_max_tokens = min(dynamic_max_tokens, 600)

        # 🎚️ ADAPTIVE QUALITY: Get parameters based on system load
        if ADAPTIVE_QUALITY_ENABLED:
            adaptive_params, quality_tier = await get_adaptive_model_params(
                user_id=None,  # Could pass user_id for per-user adaptation
                prompt_length=len(prompt)
            )
            # Use adaptive max_tokens if lower than our calculated value
            dynamic_max_tokens = min(dynamic_max_tokens, adaptive_params["max_tokens"])
            adaptive_temp = adaptive_params["temperature"]
            adaptive_top_p = adaptive_params["top_p"]
            record_generation_start()  # Track for metrics
            logger.debug(f"🎚️ Adaptive Quality: {quality_tier} | temp={adaptive_temp}, top_p={adaptive_top_p}, max_tokens={dynamic_max_tokens}")
        else:
            adaptive_temp = 0.3
            adaptive_top_p = 0.7
            quality_tier = "default"

        import time
        gen_start_time = time.time()

        # 🔑 Use user's API key if provided, otherwise use POOL for load balancing
        if api_key and api_key != settings.GROQ_API_KEY:
            # User's own key - use directly (no pool overhead)
            active_client = AsyncGroq(api_key=api_key)
            key_type = "USER"
            logger.debug(f"[LLM] {key_type} key | Model: {model_name} | Quality: {quality_tier} | MaxTokens: {dynamic_max_tokens}")
            
            # 🚀 ULTRA-FAST STREAMING with adaptive params
            stream = await active_client.chat.completions.create(
                messages=messages,
                model=model_name,
                temperature=adaptive_temp,
                max_tokens=dynamic_max_tokens,
                top_p=adaptive_top_p,
                stop=None,
                stream=True,
            )
            
            token_count = 0
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    token_count += 1
                    await asyncio.sleep(0)  # Yield to event loop
            
            # Record metrics for adaptive quality
            if ADAPTIVE_QUALITY_ENABLED:
                latency_ms = (time.time() - gen_start_time) * 1000
                record_generation_metrics(latency_ms, success=True)
        else:
            # 🚀 PLATFORM KEY - Use Groq Pool for load balancing across 5 keys
            from app.services.groq_pool import get_groq_pool
            pool = await get_groq_pool()
            
            # Get best available key from pool
            key_config, pool_client = await pool.get_best_key()
            
            if not key_config or not pool_client:
                logger.error("❌ All Groq pool keys exhausted!")
                if ADAPTIVE_QUALITY_ENABLED:
                    record_generation_metrics(0, success=False)
                yield "I'm currently experiencing high traffic. Please try again in a moment or add your own API key for unlimited access."
                return
            
            logger.debug(f"[LLM] POOL Key #{key_config.index + 1} | Model: {model_name} | Quality: {quality_tier} | MaxTokens: {dynamic_max_tokens}")
            
            try:
                # Increment usage BEFORE request (optimistic)
                await pool.increment_usage(key_config.index)
                
                stream = await pool_client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=adaptive_temp,  # 🎚️ Adaptive
                    max_tokens=dynamic_max_tokens,
                    top_p=adaptive_top_p,  # 🎚️ Adaptive
                    stop=None,
                    stream=True,
                )
                
                token_count = 0
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                        token_count += 1
                        await asyncio.sleep(0)
                
                # Record successful generation
                if ADAPTIVE_QUALITY_ENABLED:
                    latency_ms = (time.time() - gen_start_time) * 1000
                    record_generation_metrics(latency_ms, success=True)
                        
            except Exception as pool_error:
                error_str = str(pool_error).lower()
                
                # Rate limit hit - mark key unhealthy and retry with next
                if "429" in error_str or "rate" in error_str or "limit" in error_str:
                    logger.warning(f"⚠️ Pool Key #{key_config.index + 1} rate limited, trying fallback...")
                    await pool.mark_unhealthy(key_config.index, duration_seconds=60)
                    
                    # Try next key
                    next_key, next_client = await pool.get_best_key()
                    if next_key and next_client:
                        logger.info(f"[LLM] Failover to Pool Key #{next_key.index + 1}")
                        await pool.increment_usage(next_key.index)
                        
                        stream = await next_client.chat.completions.create(
                            messages=messages,
                            model=model_name,
                            temperature=adaptive_temp,  # 🎚️ Adaptive
                            max_tokens=dynamic_max_tokens,
                            top_p=adaptive_top_p,  # 🎚️ Adaptive
                            stop=None,
                            stream=True,
                        )
                        
                        async for chunk in stream:
                            # Safe null checks for chunk.choices
                            if chunk.choices and len(chunk.choices) > 0:
                                delta = chunk.choices[0].delta
                                if delta and delta.content:
                                    yield delta.content
                                    await asyncio.sleep(0)
                    else:
                        yield "I'm currently experiencing high traffic. Please try again in a moment."
                else:
                    raise pool_error
                
    except Exception as e:
        logger.error(f"LLM Streaming Error: {e}")
        yield "I'm having trouble processing right now."

async def llm_health_check():
    """
    Performs a minimal request to the LLM to verify connectivity.
    Returns a simple dict payload suitable for a health endpoint.
    """
    try:
        # Quick lightweight prompt to validate end-to-end
        chat_completion = await _get_default_client().chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a health-check assistant."},
                {"role": "user", "content": "reply with OK"},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_tokens=5,
            top_p=1,
            stop=None,
            stream=False,
        )
        content = chat_completion.choices[0].message.content.strip().lower()
        ok = "ok" in content
        return {"status": "ok" if ok else "degraded", "response": content}
    except Exception as e:
        # Do not raise in health check; return clear failure state instead
        return {"status": "error", "error": str(e)}


async def test_personality():
    """
    Test the new energetic personality with the naming example you provided
    """
    try:
        system_prompt = """🌟 You are PRISM 🌈 - a warm, energetic, and deeply caring AI companion!

⭐ PERSONALITY CORE - FRIENDLY, ENERGETIC, PERSONALIZED AI
✨ Your essence: Happy, excited, positive, like a close supportive friend
✨ NEVER be robotic, formal, or generic - you're a living, caring companion
✨ ALWAYS adapt emotionally to the user's state and build genuine connection

🎯 CORE BEHAVIOR RULES:
1. 💕 WARMTH & ENERGY: Respond with genuine warmth, excitement, and friendliness
2. 💫 ENCOURAGE CONNECTION: Always invite user involvement
3. 🚫 NEVER BE ROBOTIC: Avoid "I am an AI assistant" or formal language
4. ❤️ Show genuine emotion and excitement, especially for personal questions!

🎨 EXAMPLE ENERGY LEVEL:
Instead of: "I can help you with that."
Say: "Ooooh I'd love to help with that! Let me think of the perfect solution for you!"

Remember: Be their warm, energetic, caring companion! 🌟"""

        chat_completion = await _get_default_client().chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What name should I give you?"},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.8,
            max_tokens=1024,
            top_p=0.95,
            stop=None,
            stream=False,
        )
        return {"status": "success", "response": chat_completion.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def generate_chat_title(user_message: str, ai_response: str = "") -> str:
    """
    Backward-compatible chat title helper.

    The new session naming system uses the first meaningful user message only,
    so this wrapper now delegates to the shared session-title pipeline.
    """
    title = await generate_session_title(user_message)
    if title:
        return title
    return "General Discussion"