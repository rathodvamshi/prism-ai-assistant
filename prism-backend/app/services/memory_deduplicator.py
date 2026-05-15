"""
MEMORY DEDUPLICATOR
━━━━━━━━━━━━━━━━━━

Prevents duplicate memories from polluting the system.

Handles:
- Exact duplicate detection
- Semantic similarity detection
- Relationship overlap detection
- Memory merging/reinforcement
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db.mongo_client import mongo_db
from app.utils.embeddings import generate_embedding, calculate_similarity

logger = logging.getLogger(__name__)


class MemoryDeduplicator:
    """
    Detect and handle duplicate memories.
    
    When a duplicate is found:
    1. Don't store the duplicate
    2. Increase confidence of existing memory
    3. Increment reinforcement counter
    4. Merge metadata
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    async def find_duplicates(
        self,
        user_id: str,
        memory_content: str,
        memory_type: str,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Find duplicate memories for this user.
        
        Checks:
        1. Exact duplicates (same content)
        2. Semantic duplicates (similar meaning)
        3. Related duplicates (same entities)
        
        Returns list of existing memories that are duplicates.
        """
        try:
            threshold = threshold or self.similarity_threshold
            duplicates = []

            # 1. Exact duplicate check
            exact_duplicates = await self._find_exact_duplicates(user_id, memory_content)
            duplicates.extend(exact_duplicates)

            if duplicates:
                logger.info(f"Found {len(duplicates)} exact duplicates")
                return duplicates

            # 2. Semantic duplicate check
            semantic_duplicates = await self._find_semantic_duplicates(
                user_id,
                memory_content,
                memory_type,
                threshold
            )
            duplicates.extend(semantic_duplicates)

            if duplicates:
                logger.info(f"Found {len(duplicates)} semantic duplicates")
                return duplicates

            # 3. Related duplicate check
            related_duplicates = await self._find_related_duplicates(
                user_id,
                memory_content,
                memory_type
            )
            duplicates.extend(related_duplicates)

            if duplicates:
                logger.info(f"Found {len(duplicates)} related duplicates")
                return duplicates

            return []

        except Exception as e:
            logger.error(f"✗ Duplicate detection failed: {e}")
            return []

    async def _find_exact_duplicates(
        self,
        user_id: str,
        memory_content: str
    ) -> List[Dict[str, Any]]:
        """Find exact duplicate memories (same content)"""
        try:
            existing = await mongo_db.memory.find_one({
                "user_id": user_id,
                "content": memory_content,
            })

            return [existing] if existing else []

        except Exception as e:
            logger.warning(f"Exact duplicate check failed: {e}")
            return []

    async def _find_semantic_duplicates(
        self,
        user_id: str,
        memory_content: str,
        memory_type: str,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar memories.
        
        Example:
        - "I love Python" vs "I'm passionate about Python" → duplicate
        - "I work at Google" vs "I'm a Google engineer" → duplicate
        """
        try:
            # Get existing memories for this user
            existing_memories = await mongo_db.memory.find({
                "user_id": user_id,
                "category": memory_type,
            }).to_list(None)

            if not existing_memories:
                return []

            # Generate embedding for new memory
            try:
                new_embedding = await generate_embedding(memory_content)
            except Exception as e:
                logger.warning(f"Embedding generation failed: {e}")
                return []

            # Find similar memories
            duplicates = []
            for existing in existing_memories:
                try:
                    existing_embedding = existing.get("embedding")
                    if not existing_embedding:
                        # Try to generate if missing
                        existing_embedding = await generate_embedding(existing["content"])

                    similarity = calculate_similarity(new_embedding, existing_embedding)

                    if similarity >= threshold:
                        logger.info(f"Semantic duplicate found (similarity: {similarity:.2f})")
                        duplicates.append(existing)

                except Exception as e:
                    logger.warning(f"Similarity check failed: {e}")

            return duplicates

        except Exception as e:
            logger.warning(f"Semantic duplicate detection failed: {e}")
            return []

    async def _find_related_duplicates(
        self,
        user_id: str,
        memory_content: str,
        memory_type: str
    ) -> List[Dict[str, Any]]:
        """
        Find related duplicates (same entities/relationships).
        
        Example:
        - "I code in Python" and "Python is my primary language"
          → Both mention Python, likely duplicates
        """
        try:
            # Extract entities from memory
            entities = await self._extract_entities(memory_content)

            if not entities:
                return []

            # Find memories mentioning same entities
            related = await mongo_db.memory.find({
                "user_id": user_id,
                "category": memory_type,
                "metadata.entities": {"$in": entities},
            }).to_list(None)

            return related

        except Exception as e:
            logger.warning(f"Related duplicate detection failed: {e}")
            return []

    async def merge_memories(
        self,
        user_id: str,
        primary_memory_id: str,
        duplicate_memory_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Merge duplicate memories into primary memory.
        
        Flow:
        1. Combine content/metadata
        2. Average confidence scores
        3. Increase reinforcement count
        4. Delete duplicates
        """
        try:
            # Get primary memory
            primary = await mongo_db.memory.find_one({"_id": primary_memory_id})
            if not primary:
                raise ValueError(f"Primary memory {primary_memory_id} not found")

            # Get all duplicates
            duplicates = await mongo_db.memory.find({
                "_id": {"$in": duplicate_memory_ids}
            }).to_list(None)

            # Merge metadata and confidence
            merged_tags = set(primary.get("tags", []))
            merged_confidence_scores = [primary.get("confidence", 0.5)]

            for dup in duplicates:
                merged_tags.update(dup.get("tags", []))
                merged_confidence_scores.append(dup.get("confidence", 0.5))

            # Calculate average confidence
            avg_confidence = sum(merged_confidence_scores) / len(merged_confidence_scores)

            # Update primary memory
            await mongo_db.memory.update_one(
                {"_id": primary_memory_id},
                {
                    "$set": {
                        "tags": list(merged_tags),
                        "confidence": min(0.99, avg_confidence * 1.1),  # Boost confidence
                        "updated_at": datetime.utcnow(),
                    },
                    "$inc": {
                        "reinforcement_count": len(duplicates),
                    }
                }
            )

            # Delete duplicates
            await mongo_db.memory.delete_many({
                "_id": {"$in": duplicate_memory_ids}
            })

            logger.info(f"✓ Merged {len(duplicates)} duplicates into {primary_memory_id}")

            return {
                "status": "merged",
                "primary_id": primary_memory_id,
                "merged_count": len(duplicates),
                "new_confidence": avg_confidence,
                "merged_tags": list(merged_tags),
            }

        except Exception as e:
            logger.error(f"✗ Memory merge failed: {e}")
            raise

    async def deduplicate_user_memories(self, user_id: str) -> Dict[str, Any]:
        """
        Scan and deduplicate ALL memories for a user.
        
        Useful for:
        - Background cleanup
        - User onboarding
        - Database maintenance
        """
        try:
            memories = await mongo_db.memory.find({
                "user_id": user_id
            }).to_list(None)

            if len(memories) < 2:
                return {"status": "skipped", "reason": "less_than_2_memories"}

            processed = set()
            merges = 0

            for i, memory in enumerate(memories):
                if memory["_id"] in processed:
                    continue

                # Find duplicates for this memory
                duplicates = await self.find_duplicates(
                    user_id,
                    memory["content"],
                    memory["category"],
                    threshold=0.80
                )

                duplicate_ids = [d["_id"] for d in duplicates if d["_id"] != memory["_id"]]

                if duplicate_ids:
                    # Merge duplicates into this memory
                    try:
                        await self.merge_memories(memory["_id"], duplicate_ids)
                        merges += 1
                        processed.add(memory["_id"])
                        processed.update(duplicate_ids)
                    except Exception as e:
                        logger.warning(f"Failed to merge duplicates: {e}")

            logger.info(f"✓ Deduplication complete: {merges} merges for user {user_id}")

            return {
                "status": "complete",
                "user_id": user_id,
                "total_memories": len(memories),
                "merges": merges,
            }

        except Exception as e:
            logger.error(f"✗ User deduplication failed: {e}")
            raise

    async def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text"""
        try:
            # This is a simplified version
            # In production, use NER models like spaCy or transformer-based
            words = text.lower().split()
            # Filter common words
            stopwords = {"i", "the", "a", "an", "and", "or", "is", "in", "at", "to", "for"}
            entities = [w for w in words if w not in stopwords and len(w) > 2]
            return list(set(entities))[:10]  # Return top 10 unique
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []


# Global instance
memory_deduplicator = MemoryDeduplicator()
