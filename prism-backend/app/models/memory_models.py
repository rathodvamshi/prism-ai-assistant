"""
UNIFIED MEMORY DATA MODELS
━━━━━━━━━━━━━━━━━━━━━━━━━

MongoDB schemas for the new memory architecture:
- GLOBAL_MEMORY: Persists across all sessions
- SESSION_MEMORY: Temporary per-session context
- MINI_AGENT_MEMORY: Isolated to agent threads

These models ensure clean data ownership and consistency.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GLOBAL MEMORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GlobalMemoryModel(BaseModel):
    """
    GLOBAL MEMORY: Persists across ALL sessions.
    
    Examples:
    - User identity (name, age, location)
    - Professional info (job, skills, experience)
    - Preferences (coding language, communication style)
    - Interests (hobbies, topics)
    - Personality traits
    
    Source of truth: MongoDB
    Also cached in: Redis, Neo4j (relationships), Pinecone (vectors)
    """

    # Database
    id: str = Field(alias="_id")
    user_id: str  # Canonical user UUID

    # Memory content
    memory_type: str = Field(default="GLOBAL_MEMORY")
    category: str  # identity, skills, preferences, interests, personality, experiences
    content: str  # The actual memory text
    tags: List[str] = Field(default_factory=list)  # e.g., ["java", "python", "backend"]

    # Scoring & ranking
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)  # How confident are we (0-1)
    reinforcement_count: int = Field(default=1)  # How many times reinforced
    priority_score: float = Field(default=0.0)  # Calculated by prioritizer (0-100)

    # Metadata & tracking
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_reinforced_at: Optional[datetime] = None

    # Storage tracking
    backends: List[str] = Field(default_factory=list)  # ["mongodb", "neo4j", "pinecone", "redis"]
    is_global: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "id": "mem_123abc",
                "user_id": "user_8fa2c1",
                "memory_type": "GLOBAL_MEMORY",
                "category": "identity",
                "content": "I am Amar, a backend engineer who loves Java and Python",
                "tags": ["java", "python", "backend", "engineer"],
                "confidence": 0.95,
                "reinforcement_count": 3,
                "metadata": {"source": "conversation", "language": "English"},
                "created_at": "2024-01-15T10:30:00Z",
                "backends": ["mongodb", "neo4j", "pinecone"]
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SESSION MEMORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SessionMemoryModel(BaseModel):
    """
    SESSION MEMORY: Temporary context for current session only.
    
    Examples:
    - Current conversation topic
    - Current task being worked on
    - Session-specific notes
    - Temporary state variables
    
    TTL: Expires when session ends (usually 1-24 hours)
    
    Storage: MongoDB (with TTL index) + Redis cache
    NOT in Neo4j or Pinecone (too temporary)
    """

    # Database
    id: str = Field(alias="_id")
    user_id: str
    session_id: str  # Links to auth session

    # Memory content
    memory_type: str = Field(default="SESSION_MEMORY")
    category: str  # context, task, note, state, conversation_topic
    content: str

    # Metadata & tracking
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime  # TTL for this session memory

    # Storage tracking
    backends: List[str] = Field(default_factory=list)  # ["mongodb", "redis"]
    is_global: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "id": "sess_mem_456def",
                "user_id": "user_8fa2c1",
                "session_id": "session_xyz789",
                "memory_type": "SESSION_MEMORY",
                "category": "task",
                "content": "Currently refactoring Auth service, focusing on JWT token renewal",
                "created_at": "2024-01-15T10:30:00Z",
                "expires_at": "2024-01-16T10:30:00Z",
                "backends": ["mongodb", "redis"]
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MINI-AGENT MEMORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MiniAgentMemoryModel(BaseModel):
    """
    MINI-AGENT MEMORY: Isolated to specific agent/thread execution.
    
    Examples:
    - Agent's working memory
    - Thread-specific state
    - Intermediate computations
    - Agent's contextual notes
    
    Scope: Only accessible within that agent's execution
    TTL: 1 hour (or agent lifetime)
    
    Storage: MongoDB + Redis only
    NOT shared across agents or sessions
    """

    # Database
    id: str = Field(alias="_id")
    user_id: str
    agent_id: str  # Links to specific mini-agent instance

    # Memory content
    memory_type: str = Field(default="MINI_AGENT_MEMORY")
    content: str
    execution_context: Dict[str, Any] = Field(default_factory=dict)

    # Metadata & tracking
    created_at: datetime
    expires_at: datetime  # TTL for agent execution
    agent_state: str = Field(default="active")  # active, paused, completed, failed

    # Storage tracking
    backends: List[str] = Field(default_factory=list)  # ["mongodb", "redis"]
    is_global: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "id": "agent_mem_789ghi",
                "user_id": "user_8fa2c1",
                "agent_id": "agent_research_001",
                "memory_type": "MINI_AGENT_MEMORY",
                "content": "Found 15 Python packages for JWT auth, comparing features",
                "execution_context": {
                    "task": "find_jwt_library",
                    "progress": "45%",
                },
                "created_at": "2024-01-15T10:30:00Z",
                "expires_at": "2024-01-15T11:30:00Z",
                "agent_state": "active"
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USER CONTEXT (for LLM injection)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class UserContextModel(BaseModel):
    """
    Holographic context built from all memory types.
    
    This is what gets injected into LLM prompts
    to provide global, session, and agent context.
    """

    user_id: str
    timestamp: datetime

    # Global context (persistent across sessions)
    global_memories: List[Dict[str, Any]] = Field(default_factory=list)
    user_profile: Dict[str, Any] = Field(default_factory=dict)  # name, email, preferences
    user_relationships: List[Dict[str, Any]] = Field(default_factory=list)  # interests, skills

    # Session context (current session only)
    session_memories: List[Dict[str, Any]] = Field(default_factory=list)
    current_task: Optional[str] = None
    conversation_topic: Optional[str] = None

    # Agent context (current agent only)
    agent_memories: List[Dict[str, Any]] = Field(default_factory=list)
    agent_state: Optional[Dict[str, Any]] = None

    # Semantic context (relevant memories from search)
    semantic_memories: List[Dict[str, Any]] = Field(default_factory=list)

    # Summary for system prompt
    context_summary: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_8fa2c1",
                "timestamp": "2024-01-15T10:30:00Z",
                "global_memories": [
                    {
                        "category": "identity",
                        "content": "I'm Amar, a backend engineer"
                    }
                ],
                "user_profile": {
                    "name": "Amar",
                    "email": "amar@example.com",
                    "timezone": "Asia/Kolkata"
                },
                "session_memories": [
                    {
                        "category": "task",
                        "content": "Refactoring JWT auth service"
                    }
                ],
                "context_summary": "Amar is a backend engineer working on JWT auth. Knows Java and Python."
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMORY STATISTICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MemoryStatsModel(BaseModel):
    """Statistics about user's memory system"""

    user_id: str
    total_global_memories: int
    total_session_memories: int
    average_confidence: float
    most_recent_memory: Optional[str] = None
    most_reinforced_memory: Optional[str] = None
    memory_categories: Dict[str, int] = Field(default_factory=dict)
    last_sync_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_8fa2c1",
                "total_global_memories": 45,
                "total_session_memories": 12,
                "average_confidence": 0.87,
                "memory_categories": {
                    "identity": 5,
                    "skills": 12,
                    "preferences": 8,
                    "interests": 20
                }
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMORY EVENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MemoryEventModel(BaseModel):
    """
    Event published to Redis Streams.
    Used for event-driven synchronization.
    """

    event_id: str
    event_type: str  # MEMORY_CREATED, MEMORY_UPDATED, MEMORY_DELETED, etc.
    user_id: str
    timestamp: datetime
    data: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_abc123",
                "event_type": "MEMORY_CREATED",
                "user_id": "user_8fa2c1",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "memory_id": "mem_123abc",
                    "memory_type": "GLOBAL_MEMORY",
                    "content": "I love Python"
                }
            }
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REQUEST/RESPONSE MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class StoreGlobalMemoryRequest(BaseModel):
    """Request to store a global memory"""

    content: str = Field(..., description="The memory content")
    category: str = Field(..., description="Category: identity, skills, preferences, interests, personality")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StoreSessionMemoryRequest(BaseModel):
    """Request to store a session memory"""

    content: str
    category: str  # context, task, note, state, conversation_topic
    ttl_seconds: int = Field(default=86400)  # 24 hours
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrieveContextRequest(BaseModel):
    """Request to retrieve holographic context"""

    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class UpdateMemoryRequest(BaseModel):
    """Request to update a memory"""

    updates: Dict[str, Any]


class MemoryOperationResponse(BaseModel):
    """Response from memory operations"""

    status: str  # success, error, merged, etc.
    memory_id: Optional[str] = None
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
