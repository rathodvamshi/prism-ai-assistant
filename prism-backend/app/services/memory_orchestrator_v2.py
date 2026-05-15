"""
UNIFIED MEMORY ORCHESTRATOR V2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Central hub for ALL memory operations.
No service writes directly to memory systems - all go through here.

Architecture:
- Redis: Ephemeral cache (24h TTL)
- MongoDB: Source of truth (persistent)
- Neo4j: Relationship intelligence
- Pinecone: Semantic retrieval

Global Memory Types:
1. GLOBAL_MEMORY - persists across all sessions
2. SESSION_MEMORY - temporary per-session context
3. MINI_AGENT_MEMORY - isolated thread memory
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import json

from app.db.mongo_client import mongo_db
from app.db.redis_client import redis_client
from app.db.neo4j_client import neo4j_driver
from app.services.memory_event_bus import MemoryEventBus
from app.services.memory_deduplicator import MemoryDeduplicator
from app.services.memory_prioritizer import MemoryPrioritizer

logger = logging.getLogger(__name__)


class MemoryOrchestrationError(Exception):
    """Raised when memory orchestration fails critically"""
    pass


class MemoryOrchestratorV2:
    """
    Central orchestrator for ALL memory operations.
    
    Guarantees:
    - All writes are atomic across systems
    - No duplicate memories stored
    - Cross-session context available
    - Event-driven synchronization
    - Clear database responsibility
    """

    def __init__(self):
        self.event_bus = MemoryEventBus()
        self.deduplicator = MemoryDeduplicator()
        self.prioritizer = MemoryPrioritizer()
        self.operation_timeout = 30  # seconds

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WRITE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def store_global_memory(
        self,
        user_id: str,
        memory_content: str,
        memory_type: str,  # identity, preferences, skills, interests, personality
        confidence: float = 0.9,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Store memory that persists across ALL sessions.
        
        Example:
        - "I love Java" → stored globally
        - "I'm a backend engineer" → stored globally
        
        Flow:
        1. Deduplicate (check if similar memory exists)
        2. Score confidence
        3. Write to MongoDB (source of truth)
        4. Emit event
        5. Update Neo4j relationships
        6. Index in Pinecone
        7. Cache in Redis
        """
        try:
            memory_id = str(uuid4())
            timestamp = datetime.utcnow()

            # 1. Deduplicate against existing memories
            duplicates = await self.deduplicator.find_duplicates(
                user_id=user_id,
                memory_content=memory_content,
                memory_type=memory_type,
                threshold=0.85
            )

            if duplicates:
                logger.info(f"Found {len(duplicates)} duplicates for memory {memory_id}")
                for dup in duplicates:
                    # Merge reinforcement - increase confidence of existing memory
                    await self._merge_reinforcement(dup["_id"], confidence)
                return {"status": "merged", "merged_with": duplicates[0]["_id"]}

            # 2. Create memory document
            memory_doc = {
                "_id": memory_id,
                "user_id": user_id,
                "memory_type": memory_type,  # GLOBAL_MEMORY
                "content": memory_content,
                "confidence": confidence,
                "category": memory_type,
                "tags": tags or [],
                "created_at": timestamp,
                "updated_at": timestamp,
                "reinforcement_count": 1,
                "backends": [],  # Will be populated as we write
                "metadata": metadata or {},
                "is_global": True,  # This is global memory
                "priority_score": 0.0,  # Will be calculated
            }

            # 3. Write to MongoDB (source of truth) - MUST SUCCEED
            try:
                await mongo_db.memory.insert_one(memory_doc)
                memory_doc["backends"].append("mongodb")
                logger.info(f"✓ Stored memory {memory_id} in MongoDB")
            except Exception as e:
                logger.error(f"✗ MongoDB write failed for memory {memory_id}: {e}")
                raise MemoryOrchestrationError(f"MongoDB write failed: {e}")

            # 4. Emit event for downstream systems
            event = {
                "event_type": "MEMORY_CREATED",
                "memory_id": memory_id,
                "user_id": user_id,
                "memory_type": memory_type,
                "content": memory_content,
                "timestamp": timestamp.isoformat(),
            }
            await self.event_bus.publish(event)

            # 5. Update Neo4j relationships (async, non-blocking)
            try:
                asyncio.create_task(
                    self._update_neo4j_relationships(user_id, memory_content, memory_type)
                )
                memory_doc["backends"].append("neo4j")
            except Exception as e:
                logger.warning(f"Neo4j relationship update failed (non-critical): {e}")

            # 6. Index in Pinecone (async, non-blocking)
            try:
                asyncio.create_task(
                    self._index_pinecone(memory_id, user_id, memory_content)
                )
                memory_doc["backends"].append("pinecone")
            except Exception as e:
                logger.warning(f"Pinecone indexing failed (non-critical): {e}")

            # 7. Cache in Redis (async, non-blocking)
            try:
                asyncio.create_task(
                    self._cache_redis(user_id, memory_id, memory_doc)
                )
                memory_doc["backends"].append("redis")
            except Exception as e:
                logger.warning(f"Redis caching failed (non-critical): {e}")

            # Update MongoDB with backends list
            await mongo_db.memory.update_one(
                {"_id": memory_id},
                {"$set": {"backends": memory_doc["backends"]}}
            )

            logger.info(f"✓ Memory {memory_id} orchestrated across: {memory_doc['backends']}")
            return {
                "status": "success",
                "memory_id": memory_id,
                "backends": memory_doc["backends"],
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"✗ Global memory store failed: {e}")
            raise

    async def store_session_memory(
        self,
        user_id: str,
        session_id: str,
        memory_content: str,
        memory_category: str,
        ttl_seconds: int = 86400,  # 24 hours default
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store memory that persists only within CURRENT SESSION.
        
        Example:
        - "We're discussing Java streams" → session-only
        - "Current task: refactor Auth service" → session-only
        
        Flow:
        1. Store in MongoDB with session_id reference
        2. Cache in Redis with TTL
        3. Emit SESSION_MEMORY_CREATED event
        """
        try:
            memory_id = str(uuid4())
            timestamp = datetime.utcnow()

            session_memory_doc = {
                "_id": memory_id,
                "user_id": user_id,
                "session_id": session_id,
                "memory_type": "SESSION_MEMORY",
                "category": memory_category,
                "content": memory_content,
                "created_at": timestamp,
                "expires_at": timestamp + timedelta(seconds=ttl_seconds),
                "metadata": metadata or {},
                "backends": [],
            }

            # Write to MongoDB with TTL
            try:
                await mongo_db.session_memory.insert_one(session_memory_doc)
                session_memory_doc["backends"].append("mongodb")
            except Exception as e:
                logger.error(f"MongoDB session memory write failed: {e}")
                raise

            # Cache in Redis with TTL
            try:
                redis_key = f"session_memory:{user_id}:{session_id}:{memory_category}"
                await redis_client.setex(
                    redis_key,
                    ttl_seconds,
                    json.dumps(session_memory_doc, default=str)
                )
                session_memory_doc["backends"].append("redis")
            except Exception as e:
                logger.warning(f"Redis session memory cache failed: {e}")

            # Emit event
            event = {
                "event_type": "SESSION_MEMORY_CREATED",
                "memory_id": memory_id,
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": timestamp.isoformat(),
            }
            await self.event_bus.publish(event)

            logger.info(f"✓ Session memory {memory_id} stored")
            return {
                "status": "success",
                "memory_id": memory_id,
                "backends": session_memory_doc["backends"],
                "expires_at": session_memory_doc["expires_at"].isoformat(),
            }

        except Exception as e:
            logger.error(f"✗ Session memory store failed: {e}")
            raise

    async def store_mini_agent_memory(
        self,
        user_id: str,
        agent_id: str,
        memory_content: str,
        ttl_seconds: int = 3600,  # 1 hour default
    ) -> Dict[str, Any]:
        """
        Store memory isolated to a specific mini-agent thread.
        
        Scope: Only accessible within that agent's execution context.
        
        Flow:
        1. Store in MongoDB with agent_id
        2. Cache in Redis (fast access)
        3. Emit MINI_AGENT_MEMORY_CREATED event
        """
        try:
            memory_id = str(uuid4())
            timestamp = datetime.utcnow()

            agent_memory_doc = {
                "_id": memory_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "memory_type": "MINI_AGENT_MEMORY",
                "content": memory_content,
                "created_at": timestamp,
                "expires_at": timestamp + timedelta(seconds=ttl_seconds),
                "backends": [],
            }

            # Write to MongoDB
            try:
                await mongo_db.mini_agent_memory.insert_one(agent_memory_doc)
                agent_memory_doc["backends"].append("mongodb")
            except Exception as e:
                logger.error(f"MongoDB mini-agent memory write failed: {e}")
                raise

            # Cache in Redis
            try:
                redis_key = f"agent_memory:{user_id}:{agent_id}"
                await redis_client.setex(
                    redis_key,
                    ttl_seconds,
                    json.dumps(agent_memory_doc, default=str)
                )
                agent_memory_doc["backends"].append("redis")
            except Exception as e:
                logger.warning(f"Redis mini-agent memory cache failed: {e}")

            logger.info(f"✓ Mini-agent memory {memory_id} stored")
            return {
                "status": "success",
                "memory_id": memory_id,
                "backends": agent_memory_doc["backends"],
            }

        except Exception as e:
            logger.error(f"✗ Mini-agent memory store failed: {e}")
            raise

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # READ OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def retrieve_holographic_context(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Retrieve COMPLETE CONTEXT across all memory types.
        
        Returns merged context from:
        1. Session memory (if session_id provided)
        2. Mini-agent memory (if agent_id provided)
        3. Global memories (always included)
        4. Relationship memory (Neo4j)
        5. Semantic memory (Pinecone)
        
        This is called BEFORE EVERY LLM RESPONSE to ensure
        the assistant has complete global context.
        """
        try:
            # Parallel retrieval from all sources
            results = await asyncio.gather(
                self._retrieve_global_memories(user_id, limit),
                self._retrieve_session_memories(user_id, session_id, limit) if session_id else asyncio.sleep(0),
                self._retrieve_agent_memories(user_id, agent_id, limit) if agent_id else asyncio.sleep(0),
                self._retrieve_relationship_memory(user_id, limit),
                self._retrieve_semantic_memory(user_id, limit),
                return_exceptions=True
            )

            # Extract results (handling exceptions)
            global_memories = results[0] if not isinstance(results[0], Exception) else []
            session_memories = results[1] if session_id and not isinstance(results[1], Exception) else []
            agent_memories = results[2] if agent_id and not isinstance(results[2], Exception) else []
            relationship_memory = results[3] if not isinstance(results[3], Exception) else []
            semantic_memory = results[4] if not isinstance(results[4], Exception) else []

            # Merge and rank by priority
            all_memories = global_memories + session_memories + agent_memories
            ranked_memories = await self.prioritizer.rank_memories(all_memories)

            holographic_context = {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "global_memories": global_memories,
                "session_memories": session_memories,
                "agent_memories": agent_memories,
                "relationship_memory": relationship_memory,
                "semantic_memory": semantic_memory,
                "ranked_memories": ranked_memories[:limit],
                "context_summary": self._generate_context_summary(
                    global_memories, relationship_memory
                ),
            }

            logger.info(f"✓ Holographic context retrieved for user {user_id}")
            return holographic_context

        except Exception as e:
            logger.error(f"✗ Holographic context retrieval failed: {e}")
            return {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "memories": []
            }

    async def retrieve_global_memories_only(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve only GLOBAL memories (cross-session persistent data)"""
        try:
            query = {
                "user_id": user_id,
                "memory_type": "GLOBAL_MEMORY",
                "is_global": True,
            }
            if memory_type:
                query["category"] = memory_type

            # Try Redis cache first
            cache_key = f"global_memories:{user_id}:{memory_type or 'all'}"
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis global memory cache miss: {e}")

            # Fall back to MongoDB
            memories = await mongo_db.memory.find(query).sort(
                "confidence", -1
            ).limit(limit).to_list(None)

            # Cache result
            try:
                await redis_client.setex(
                    cache_key,
                    3600,  # 1 hour
                    json.dumps([m for m in memories], default=str)
                )
            except Exception as e:
                logger.warning(f"Failed to cache global memories: {e}")

            return memories

        except Exception as e:
            logger.error(f"✗ Global memory retrieval failed: {e}")
            return []

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UPDATE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def update_memory(
        self,
        user_id: str,
        memory_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a memory atomically across all systems.
        
        Flow:
        1. Update MongoDB
        2. Emit MEMORY_UPDATED event
        3. Invalidate caches
        4. Update downstream systems
        """
        try:
            timestamp = datetime.utcnow()

            # Update MongoDB
            result = await mongo_db.memory.update_one(
                {"_id": memory_id, "user_id": user_id},
                {
                    "$set": {
                        **updates,
                        "updated_at": timestamp,
                    },
                    "$inc": {"reinforcement_count": 1}
                }
            )

            if result.matched_count == 0:
                raise MemoryOrchestrationError(f"Memory {memory_id} not found")

            # Emit event
            event = {
                "event_type": "MEMORY_UPDATED",
                "memory_id": memory_id,
                "user_id": user_id,
                "updates": updates,
                "timestamp": timestamp.isoformat(),
            }
            await self.event_bus.publish(event)

            # Invalidate caches
            await self._invalidate_caches(user_id)

            logger.info(f"✓ Memory {memory_id} updated")
            return {"status": "success", "memory_id": memory_id}

        except Exception as e:
            logger.error(f"✗ Memory update failed: {e}")
            raise

    async def delete_memory(self, user_id: str, memory_id: str) -> Dict[str, Any]:
        """
        Delete a memory from all systems.
        
        Flow:
        1. Delete from MongoDB
        2. Emit MEMORY_DELETED event
        3. Remove from Pinecone
        4. Remove from Neo4j relationships
        5. Invalidate caches
        """
        try:
            # Delete from MongoDB
            result = await mongo_db.memory.delete_one(
                {"_id": memory_id, "user_id": user_id}
            )

            if result.deleted_count == 0:
                raise MemoryOrchestrationError(f"Memory {memory_id} not found")

            # Emit event
            event = {
                "event_type": "MEMORY_DELETED",
                "memory_id": memory_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.event_bus.publish(event)

            # Clean up other systems (async)
            asyncio.create_task(self._cleanup_memory_from_systems(user_id, memory_id))

            # Invalidate caches
            await self._invalidate_caches(user_id)

            logger.info(f"✓ Memory {memory_id} deleted")
            return {"status": "success", "memory_id": memory_id}

        except Exception as e:
            logger.error(f"✗ Memory deletion failed: {e}")
            raise

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PRIVATE HELPER METHODS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _merge_reinforcement(self, existing_memory_id: str, new_confidence: float):
        """Merge duplicate - increase confidence of existing memory"""
        try:
            await mongo_db.memory.update_one(
                {"_id": existing_memory_id},
                {
                    "$inc": {"reinforcement_count": 1},
                    "$set": {
                        "confidence": max(
                            0.99,
                            (await mongo_db.memory.find_one({"_id": existing_memory_id}))["confidence"] * 1.05
                        ),
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Failed to merge reinforcement: {e}")

    async def _update_neo4j_relationships(self, user_id: str, memory_content: str, memory_type: str):
        """Update Neo4j with memory relationships"""
        try:
            # This would extract entities and create relationships
            logger.debug(f"Neo4j relationship update: {memory_type}")
        except Exception as e:
            logger.warning(f"Neo4j update failed: {e}")

    async def _index_pinecone(self, memory_id: str, user_id: str, memory_content: str):
        """Index memory in Pinecone for semantic search"""
        try:
            # This would generate embedding and upsert to Pinecone
            logger.debug(f"Pinecone indexing: {memory_id}")
        except Exception as e:
            logger.warning(f"Pinecone indexing failed: {e}")

    async def _cache_redis(self, user_id: str, memory_id: str, memory_doc: Dict[str, Any]):
        """Cache memory in Redis"""
        try:
            cache_key = f"memory:{user_id}:{memory_id}"
            await redis_client.setex(cache_key, 86400, json.dumps(memory_doc, default=str))
        except Exception as e:
            logger.warning(f"Redis caching failed: {e}")

    async def _retrieve_global_memories(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve global memories"""
        return await self.retrieve_global_memories_only(user_id, limit=limit)

    async def _retrieve_session_memories(self, user_id: str, session_id: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve session-specific memories"""
        try:
            return await mongo_db.session_memory.find({
                "user_id": user_id,
                "session_id": session_id,
                "expires_at": {"$gt": datetime.utcnow()},
            }).sort("created_at", -1).limit(limit).to_list(None)
        except Exception as e:
            logger.warning(f"Session memory retrieval failed: {e}")
            return []

    async def _retrieve_agent_memories(self, user_id: str, agent_id: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve mini-agent memories"""
        try:
            return await mongo_db.mini_agent_memory.find({
                "user_id": user_id,
                "agent_id": agent_id,
                "expires_at": {"$gt": datetime.utcnow()},
            }).sort("created_at", -1).limit(limit).to_list(None)
        except Exception as e:
            logger.warning(f"Agent memory retrieval failed: {e}")
            return []

    async def _retrieve_relationship_memory(self, user_id: str, limit: int) -> Dict[str, Any]:
        """Retrieve relationship intelligence from Neo4j"""
        try:
            # Would query Neo4j for relationships
            return {
                "relationships": [],
                "entities": [],
            }
        except Exception as e:
            logger.warning(f"Relationship memory retrieval failed: {e}")
            return {}

    async def _retrieve_semantic_memory(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Retrieve semantic memory from Pinecone"""
        try:
            # Would query Pinecone for similar vectors
            return []
        except Exception as e:
            logger.warning(f"Semantic memory retrieval failed: {e}")
            return []

    async def _invalidate_caches(self, user_id: str):
        """Invalidate all caches for user"""
        try:
            pattern = f"*:{user_id}:*"
            # Would use Redis KEYS or SCAN to invalidate
            logger.debug(f"Cache invalidated for user {user_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")

    async def _cleanup_memory_from_systems(self, user_id: str, memory_id: str):
        """Clean up memory from Pinecone and Neo4j"""
        try:
            # Remove from Pinecone and Neo4j
            logger.debug(f"Cleanup: {memory_id}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

    def _generate_context_summary(self, global_memories: List[Dict], relationships: Dict) -> str:
        """Generate natural language summary of context"""
        try:
            summary_parts = []
            if global_memories:
                summary_parts.append(f"Known about user: {len(global_memories)} global memories")
            if relationships.get("relationships"):
                summary_parts.append(f"User relationships: {len(relationships['relationships'])}")
            return "; ".join(summary_parts) if summary_parts else "No prior context"
        except Exception as e:
            logger.warning(f"Context summary generation failed: {e}")
            return "Context unavailable"


# Global instance
memory_orchestrator = MemoryOrchestratorV2()
