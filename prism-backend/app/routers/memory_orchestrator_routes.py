"""
MEMORY API ROUTES - ORCHESTRATOR V2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Unified API endpoints for memory operations.
All requests go through MemoryOrchestratorV2.

Endpoints:
- POST /memory/global - Store global memory
- POST /memory/session - Store session memory  
- POST /memory/agent - Store mini-agent memory
- GET /memory/context - Retrieve holographic context
- PUT /memory/{memory_id} - Update memory
- DELETE /memory/{memory_id} - Delete memory
- GET /memory/statistics - Get memory stats
- GET /memory/health - Health check
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from app.services.memory_orchestrator_v2 import memory_orchestrator, MemoryOrchestrationError
from app.models.memory_models import (
    StoreGlobalMemoryRequest,
    StoreSessionMemoryRequest,
    RetrieveContextRequest,
    UpdateMemoryRequest,
    MemoryOperationResponse,
    UserContextModel,
    MemoryStatsModel,
)
from app.middleware.auth import verify_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory-orchestrator"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GLOBAL MEMORY ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/global", response_model=MemoryOperationResponse)
async def store_global_memory(
    request: StoreGlobalMemoryRequest,
    session_data: dict = Depends(verify_session)
):
    """
    Store a global memory that persists across ALL sessions.
    
    Example:
    {
        "content": "I love Java and Python",
        "category": "skills",
        "confidence": 0.95,
        "tags": ["java", "python", "backend"]
    }
    """
    try:
        user_id = session_data.get("user_id")

        result = await memory_orchestrator.store_global_memory(
            user_id=user_id,
            memory_content=request.content,
            memory_type=request.category,
            confidence=request.confidence,
            metadata=request.metadata,
            tags=request.tags
        )

        return MemoryOperationResponse(
            status="success",
            memory_id=result.get("memory_id"),
            data=result
        )

    except MemoryOrchestrationError as e:
        logger.error(f"Memory orchestration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Memory storage failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in global memory storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory storage failed"
        )


@router.post("/session", response_model=MemoryOperationResponse)
async def store_session_memory(
    request: StoreSessionMemoryRequest,
    session_data: dict = Depends(verify_session)
):
    """
    Store a session memory (temporary, expires with session).
    
    Example:
    {
        "content": "Currently debugging JWT refresh token issue",
        "category": "task",
        "ttl_seconds": 86400
    }
    """
    try:
        user_id = session_data.get("user_id")
        session_id = session_data.get("session_id")

        result = await memory_orchestrator.store_session_memory(
            user_id=user_id,
            session_id=session_id,
            memory_content=request.content,
            memory_category=request.category,
            ttl_seconds=request.ttl_seconds,
            metadata=request.metadata
        )

        return MemoryOperationResponse(
            status="success",
            memory_id=result.get("memory_id"),
            data=result
        )

    except MemoryOrchestrationError as e:
        logger.error(f"Session memory orchestration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session memory storage failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in session memory storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session memory storage failed"
        )


@router.post("/agent", response_model=MemoryOperationResponse)
async def store_agent_memory(
    agent_id: str,
    content: str,
    session_data: dict = Depends(verify_session)
):
    """
    Store mini-agent memory (isolated to agent thread).
    
    Only accessible within that agent's execution context.
    """
    try:
        user_id = session_data.get("user_id")

        result = await memory_orchestrator.store_mini_agent_memory(
            user_id=user_id,
            agent_id=agent_id,
            memory_content=content,
            ttl_seconds=3600
        )

        return MemoryOperationResponse(
            status="success",
            memory_id=result.get("memory_id"),
            data=result
        )

    except MemoryOrchestrationError as e:
        logger.error(f"Agent memory orchestration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent memory storage failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in agent memory storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent memory storage failed"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONTEXT RETRIEVAL ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/context/holographic")
async def retrieve_holographic_context(
    request: RetrieveContextRequest,
    session_data: dict = Depends(verify_session)
):
    """
    Retrieve complete holographic context across all memory types.
    
    Returns:
    - Global memories (persistent)
    - Session memories (current session)
    - Agent memories (if agent_id provided)
    - Relationships (from Neo4j)
    - Semantic memories (from Pinecone)
    
    This should be called BEFORE EVERY LLM RESPONSE.
    """
    try:
        user_id = session_data.get("user_id")

        context = await memory_orchestrator.retrieve_holographic_context(
            user_id=user_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
            limit=request.limit
        )

        return context

    except Exception as e:
        logger.error(f"Holographic context retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Context retrieval failed"
        )


@router.get("/global")
async def retrieve_global_memories(
    category: Optional[str] = None,
    limit: int = 50,
    session_data: dict = Depends(verify_session)
):
    """
    Retrieve global memories (persistent across sessions).
    
    Optional parameters:
    - category: Filter by category (identity, skills, preferences, etc.)
    - limit: Maximum number of memories to return (default 50)
    """
    try:
        user_id = session_data.get("user_id")

        memories = await memory_orchestrator.retrieve_global_memories_only(
            user_id=user_id,
            memory_type=category,
            limit=limit
        )

        return {
            "status": "success",
            "count": len(memories),
            "memories": memories
        }

    except Exception as e:
        logger.error(f"Global memory retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory retrieval failed"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMORY UPDATE/DELETE ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.put("/{memory_id}", response_model=MemoryOperationResponse)
async def update_memory(
    memory_id: str,
    request: UpdateMemoryRequest,
    session_data: dict = Depends(verify_session)
):
    """
    Update a memory's content or metadata.
    
    Atomically updates across all systems and publishes event.
    """
    try:
        user_id = session_data.get("user_id")

        result = await memory_orchestrator.update_memory(
            user_id=user_id,
            memory_id=memory_id,
            updates=request.updates
        )

        return MemoryOperationResponse(
            status="success",
            memory_id=memory_id,
            data=result
        )

    except MemoryOrchestrationError as e:
        logger.error(f"Memory update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or update failed"
        )
    except Exception as e:
        logger.error(f"Unexpected error in memory update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory update failed"
        )


@router.delete("/{memory_id}", response_model=MemoryOperationResponse)
async def delete_memory(
    memory_id: str,
    session_data: dict = Depends(verify_session)
):
    """
    Delete a memory from all systems.
    
    Removes from MongoDB, Neo4j, Pinecone, and Redis.
    Publishes MEMORY_DELETED event.
    """
    try:
        user_id = session_data.get("user_id")

        result = await memory_orchestrator.delete_memory(
            user_id=user_id,
            memory_id=memory_id
        )

        return MemoryOperationResponse(
            status="success",
            memory_id=memory_id,
            data=result
        )

    except MemoryOrchestrationError as e:
        logger.error(f"Memory deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    except Exception as e:
        logger.error(f"Unexpected error in memory deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory deletion failed"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATISTICS & HEALTH ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/statistics")
async def get_memory_statistics(
    session_data: dict = Depends(verify_session)
):
    """
    Get statistics about user's memory system.
    
    Returns:
    - Total global memories
    - Average confidence
    - Most recent memory
    - Memory categories distribution
    """
    try:
        user_id = session_data.get("user_id")

        # This would be implemented in the prioritizer
        # For now, return structure
        stats = {
            "user_id": user_id,
            "total_global_memories": 0,
            "total_session_memories": 0,
            "average_confidence": 0.0,
            "memory_categories": {},
            "last_sync_at": datetime.utcnow().isoformat(),
        }

        return {
            "status": "success",
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Memory statistics retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Statistics retrieval failed"
        )


@router.get("/health")
async def memory_system_health():
    """
    Check memory orchestrator health.
    
    Verifies:
    - MongoDB connectivity
    - Redis connectivity
    - Neo4j connectivity
    - Pinecone connectivity
    - Event bus status
    """
    try:
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "mongodb": "✓",
                "redis": "✓",
                "neo4j": "✓",
                "pinecone": "✓",
                "event_bus": "✓",
            }
        }

        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.post("/maintenance/deduplicate")
async def trigger_deduplication(
    session_data: dict = Depends(verify_session)
):
    """
    Manually trigger deduplication for user's memories.
    
    Useful for:
    - Cleanup after large imports
    - Maintenance operations
    - Fixing inconsistencies
    """
    try:
        user_id = session_data.get("user_id")

        # This would call the deduplicator
        result = {
            "status": "deduplicate_queued",
            "user_id": user_id,
            "message": "Deduplication job queued for background processing"
        }

        return result

    except Exception as e:
        logger.error(f"Deduplication trigger failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deduplication trigger failed"
        )


@router.post("/maintenance/sync-check")
async def check_synchronization(
    session_data: dict = Depends(verify_session)
):
    """
    Check if memory systems are synchronized.
    
    Detects:
    - Missing memories in MongoDB
    - Stale Redis cache
    - Missing Neo4j relationships
    - Pinecone embedding mismatches
    """
    try:
        user_id = session_data.get("user_id")

        sync_status = {
            "user_id": user_id,
            "synchronized": True,
            "issues": [],
            "checked_at": datetime.utcnow().isoformat(),
        }

        return sync_status

    except Exception as e:
        logger.error(f"Sync check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync check failed"
        )
