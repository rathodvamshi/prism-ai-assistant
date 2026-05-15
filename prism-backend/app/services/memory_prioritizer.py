"""
MEMORY PRIORITIZER
━━━━━━━━━━━━━━━━━

Ranks memories by importance and relevance.

Priority Factors:
- Recency (when was it created/updated)
- Confidence (how sure are we about it)
- Explicitness (how directly stated it is)
- Reinforcement (how many times reinforced)
- Emotional importance (how important to user)
- Semantic relevance (how relevant to current context)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math

from app.db.mongo_client import mongo_db

logger = logging.getLogger(__name__)


class MemoryPrioritizer:
    """
    Rank and prioritize memories for context injection.
    
    Ensures most relevant memories are used for LLM context.
    Avoids injecting irrelevant or outdated memories.
    """

    def __init__(self):
        # Weight factors for priority calculation
        self.weights = {
            "recency": 0.20,
            "confidence": 0.25,
            "reinforcement": 0.15,
            "emotional_importance": 0.15,
            "explicitness": 0.15,
            "semantic_relevance": 0.10,
        }

    async def rank_memories(
        self,
        memories: List[Dict[str, Any]],
        context: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank memories by priority score.
        
        Returns memories sorted by priority (highest first).
        """
        try:
            ranked = []

            for memory in memories:
                try:
                    priority_score = await self._calculate_priority_score(
                        memory,
                        context
                    )
                    memory["priority_score"] = priority_score
                    ranked.append(memory)
                except Exception as e:
                    logger.warning(f"Failed to calculate priority for memory: {e}")
                    memory["priority_score"] = 0
                    ranked.append(memory)

            # Sort by priority score (descending)
            ranked.sort(key=lambda m: m.get("priority_score", 0), reverse=True)

            if limit:
                ranked = ranked[:limit]

            return ranked

        except Exception as e:
            logger.error(f"✗ Memory ranking failed: {e}")
            return memories

    async def _calculate_priority_score(
        self,
        memory: Dict[str, Any],
        context: Optional[str] = None
    ) -> float:
        """
        Calculate priority score for a single memory.
        
        Score ranges from 0-100.
        """
        try:
            score = 0.0

            # 1. Recency (0-25 points)
            recency_points = self._calculate_recency_score(memory)
            score += recency_points * self.weights["recency"]

            # 2. Confidence (0-25 points)
            confidence = memory.get("confidence", 0.5)
            confidence_points = confidence * 100
            score += confidence_points * self.weights["confidence"]

            # 3. Reinforcement (0-15 points)
            reinforcement_points = self._calculate_reinforcement_score(memory)
            score += reinforcement_points * self.weights["reinforcement"]

            # 4. Emotional importance (0-15 points)
            emotional_points = self._calculate_emotional_importance(memory)
            score += emotional_points * self.weights["emotional_importance"]

            # 5. Explicitness (0-15 points)
            explicitness_points = self._calculate_explicitness(memory)
            score += explicitness_points * self.weights["explicitness"]

            # 6. Semantic relevance (0-10 points)
            if context:
                semantic_points = await self._calculate_semantic_relevance(memory, context)
                score += semantic_points * self.weights["semantic_relevance"]

            return min(100.0, max(0.0, score))

        except Exception as e:
            logger.warning(f"Priority calculation failed: {e}")
            return 0.0

    def _calculate_recency_score(self, memory: Dict[str, Any]) -> float:
        """
        Score based on when memory was created/updated.
        
        More recent = higher score
        Decay over time.
        """
        try:
            now = datetime.utcnow()
            updated_at = memory.get("updated_at", memory.get("created_at"))

            if not updated_at:
                return 50.0  # Default mid-score

            # Convert to datetime if string
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)

            age_days = (now - updated_at).days

            # Scoring:
            # - 0-7 days: 100 points
            # - 7-30 days: 80 points
            # - 30-90 days: 60 points
            # - 90+ days: decay
            if age_days <= 7:
                return 100.0
            elif age_days <= 30:
                return 80.0
            elif age_days <= 90:
                return 60.0
            else:
                # Exponential decay
                return max(10.0, 100.0 * math.exp(-0.01 * (age_days - 90)))

        except Exception as e:
            logger.warning(f"Recency score calculation failed: {e}")
            return 50.0

    def _calculate_reinforcement_score(self, memory: Dict[str, Any]) -> float:
        """
        Score based on how many times memory was reinforced.
        
        More reinforcements = higher score (memory is important to user)
        """
        try:
            reinforcement_count = memory.get("reinforcement_count", 1)

            # Scoring:
            # - 1 reinforcement: 20 points
            # - 2-5 reinforcements: 40 points
            # - 6-10 reinforcements: 70 points
            # - 11+ reinforcements: 100 points
            if reinforcement_count <= 1:
                return 20.0
            elif reinforcement_count <= 5:
                return 40.0
            elif reinforcement_count <= 10:
                return 70.0
            else:
                return 100.0

        except Exception as e:
            logger.warning(f"Reinforcement score calculation failed: {e}")
            return 50.0

    def _calculate_emotional_importance(self, memory: Dict[str, Any]) -> float:
        """
        Score based on emotional importance tags.
        
        Example tags: critical, important, cherished, traumatic
        """
        try:
            tags = memory.get("tags", [])
            metadata = memory.get("metadata", {})

            emotional_tags = {
                "critical": 100.0,
                "important": 80.0,
                "cherished": 70.0,
                "positive": 60.0,
                "negative": 50.0,
                "neutral": 30.0,
            }

            for tag in tags:
                if tag.lower() in emotional_tags:
                    return emotional_tags[tag.lower()]

            # Check metadata for importance flag
            if metadata.get("is_important"):
                return 70.0

            return 40.0

        except Exception as e:
            logger.warning(f"Emotional importance calculation failed: {e}")
            return 40.0

    def _calculate_explicitness(self, memory: Dict[str, Any]) -> float:
        """
        Score based on how directly the memory is stated.
        
        Example:
        - "My name is John" → very explicit (100)
        - "People call me John" → somewhat explicit (70)
        - "I think people might call me John" → implicit (40)
        """
        try:
            content = memory.get("content", "").lower()

            # Check for explicit statement indicators
            explicit_phrases = [
                "my name is",
                "i am",
                "i love",
                "i hate",
                "i prefer",
                "i work",
                "i'm",
            ]

            for phrase in explicit_phrases:
                if phrase in content:
                    return 100.0

            # Check for somewhat explicit indicators
            somewhat_phrases = [
                "i like",
                "i enjoy",
                "i believe",
                "i think",
                "people say",
                "they call me",
            ]

            for phrase in somewhat_phrases:
                if phrase in content:
                    return 70.0

            return 40.0

        except Exception as e:
            logger.warning(f"Explicitness calculation failed: {e}")
            return 40.0

    async def _calculate_semantic_relevance(
        self,
        memory: Dict[str, Any],
        context: str
    ) -> float:
        """
        Score based on semantic relevance to current context.
        
        Useful for prioritizing relevant memories during conversation.
        """
        try:
            # This would use embedding similarity
            # For now, simple keyword matching
            memory_content = memory.get("content", "").lower()
            context_lower = context.lower()

            # Count keyword overlap
            memory_words = set(memory_content.split())
            context_words = set(context_lower.split())

            overlap = memory_words.intersection(context_words)
            overlap_ratio = len(overlap) / max(len(memory_words), 1)

            return min(100.0, overlap_ratio * 200)

        except Exception as e:
            logger.warning(f"Semantic relevance calculation failed: {e}")
            return 50.0

    async def get_top_memories_for_context(
        self,
        user_id: str,
        context: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top N memories most relevant to current context.
        
        Used before generating LLM response to inject
        most relevant context.
        """
        try:
            # Get all global memories for user
            all_memories = await mongo_db.memory.find({
                "user_id": user_id,
                "is_global": True,
            }).to_list(None)

            # Rank by relevance
            ranked = await self.rank_memories(all_memories, context)

            return ranked[:limit]

        except Exception as e:
            logger.error(f"✗ Failed to get top memories: {e}")
            return []

    async def get_memory_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about user's memories"""
        try:
            memories = await mongo_db.memory.find({
                "user_id": user_id,
                "is_global": True,
            }).to_list(None)

            if not memories:
                return {
                    "total_memories": 0,
                    "statistics": "No memories found",
                }

            # Calculate statistics
            avg_confidence = sum(m.get("confidence", 0.5) for m in memories) / len(memories)
            avg_reinforcement = sum(m.get("reinforcement_count", 1) for m in memories) / len(memories)
            total_reinforcements = sum(m.get("reinforcement_count", 0) for m in memories)

            # Find most recent
            newest = max(memories, key=lambda m: m.get("updated_at", datetime.utcnow()))

            # Find most reinforced
            most_reinforced = max(memories, key=lambda m: m.get("reinforcement_count", 0))

            return {
                "total_memories": len(memories),
                "average_confidence": round(avg_confidence, 3),
                "average_reinforcement": round(avg_reinforcement, 2),
                "total_reinforcements": total_reinforcements,
                "most_recent": {
                    "content": newest.get("content", ""),
                    "age_days": (datetime.utcnow() - newest.get("updated_at", datetime.utcnow())).days,
                },
                "most_reinforced": {
                    "content": most_reinforced.get("content", ""),
                    "reinforcement_count": most_reinforced.get("reinforcement_count", 0),
                },
                "memory_categories": self._get_category_distribution(memories),
            }

        except Exception as e:
            logger.error(f"✗ Memory statistics retrieval failed: {e}")
            return {}

    def _get_category_distribution(self, memories: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get distribution of memories by category"""
        distribution = {}
        for memory in memories:
            category = memory.get("category", "unknown")
            distribution[category] = distribution.get(category, 0) + 1
        return distribution


# Global instance
memory_prioritizer = MemoryPrioritizer()
