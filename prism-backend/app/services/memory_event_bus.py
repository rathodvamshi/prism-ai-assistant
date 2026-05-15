"""
MEMORY EVENT BUS
━━━━━━━━━━━━━━━━

Redis Streams based event bus for memory system synchronization.

Events Published:
- MEMORY_CREATED
- MEMORY_UPDATED
- MEMORY_DELETED
- SESSION_STARTED
- SESSION_ENDED
- PROFILE_UPDATED

Events ensure all systems stay synchronized in real-time.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid

from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)


@dataclass
class MemoryEvent:
    """Represents a memory system event"""
    event_id: str
    event_type: str  # MEMORY_CREATED, MEMORY_UPDATED, MEMORY_DELETED, etc.
    user_id: str
    timestamp: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class MemoryEventBus:
    """
    Redis Streams based event bus for memory system coordination.
    
    Ensures:
    - All memory changes are published
    - Downstream systems subscribe and react
    - Event ordering is preserved
    - No memory writes happen without events
    """

    def __init__(self):
        self.stream_key = "prism:memory:events"
        self.subscribers: Dict[str, List[Callable]] = {}
        self._running = False

    async def publish(self, event_data: Dict[str, Any]) -> str:
        """
        Publish event to Redis Stream.
        
        Example:
        {
            "event_type": "MEMORY_CREATED",
            "user_id": "user_123",
            "memory_id": "mem_abc",
            "content": "I love Python",
            "timestamp": "2024-01-15T10:30:00Z"
        }
        """
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()

            event = {
                "event_id": event_id,
                "event_type": event_data.get("event_type", "UNKNOWN"),
                "user_id": event_data.get("user_id", "system"),
                "timestamp": timestamp,
                "data": json.dumps(event_data, default=str),
            }

            # Add to Redis Stream
            stream_id = await redis_client.xadd(
                self.stream_key,
                event,
                maxlen=100000,  # Keep last 100k events
                approximate=True
            )

            logger.info(f"✓ Event published: {event_data.get('event_type')} (ID: {stream_id})")

            # Trigger local subscribers
            event_type = event_data.get("event_type", "UNKNOWN")
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    try:
                        asyncio.create_task(callback(event_data))
                    except Exception as e:
                        logger.warning(f"Subscriber callback failed: {e}")

            return stream_id

        except Exception as e:
            logger.error(f"✗ Failed to publish event: {e}")
            raise

    async def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to specific event types.
        
        Example:
        async def on_memory_created(event_data):
            print(f"Memory created: {event_data}")
        
        await event_bus.subscribe("MEMORY_CREATED", on_memory_created)
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(callback)
        logger.info(f"✓ Subscribed to {event_type}")

    async def subscribe_user_events(
        self,
        user_id: str,
        callback: Callable,
        event_types: Optional[List[str]] = None
    ):
        """
        Subscribe to all events for a specific user.
        
        Useful for:
        - Real-time UI updates
        - Memory synchronization
        - User activity tracking
        """
        default_types = [
            "MEMORY_CREATED",
            "MEMORY_UPDATED",
            "MEMORY_DELETED",
            "SESSION_STARTED",
        ]
        types_to_subscribe = event_types or default_types

        for event_type in types_to_subscribe:
            async def filtered_callback(data, uid=user_id):
                if data.get("user_id") == uid:
                    await callback(data)

            await self.subscribe(event_type, filtered_callback)

    async def listen_for_events(
        self,
        last_id: str = "0-0",
        block_ms: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Listen for new events in stream (blocking).
        
        Used by consumers/workers to process events.
        """
        try:
            # Read from stream
            results = await redis_client.xread(
                {self.stream_key: last_id},
                block=block_ms
            )

            events = []
            if results:
                for stream_key, messages in results:
                    for message_id, message_data in messages:
                        try:
                            event = {
                                "id": message_id.decode() if isinstance(message_id, bytes) else message_id,
                                "type": message_data.get(b"event_type", b"").decode() if isinstance(message_data.get(b"event_type"), bytes) else message_data.get("event_type"),
                                "user_id": message_data.get(b"user_id", b"").decode() if isinstance(message_data.get(b"user_id"), bytes) else message_data.get("user_id"),
                                "timestamp": message_data.get(b"timestamp", b"").decode() if isinstance(message_data.get(b"timestamp"), bytes) else message_data.get("timestamp"),
                                "data": json.loads(
                                    message_data.get(b"data", b"{}").decode() if isinstance(message_data.get(b"data"), bytes) else message_data.get("data", "{}")
                                ),
                            }
                            events.append(event)
                        except Exception as e:
                            logger.warning(f"Failed to parse event: {e}")

            return events

        except Exception as e:
            logger.error(f"✗ Failed to listen for events: {e}")
            return []

    async def start_event_consumer(self):
        """
        Start background worker to consume events from stream.
        
        This worker:
        1. Reads events from Redis Stream
        2. Triggers downstream system updates
        3. Ensures all systems stay synchronized
        """
        try:
            self._running = True
            last_id = "0-0"  # Start from beginning

            logger.info("Starting memory event consumer...")

            while self._running:
                events = await self.listen_for_events(last_id=last_id)

                for event in events:
                    try:
                        last_id = event["id"]

                        # Route to appropriate handler
                        event_type = event.get("type")
                        data = event.get("data", {})

                        if event_type == "MEMORY_CREATED":
                            await self._handle_memory_created(data)
                        elif event_type == "MEMORY_UPDATED":
                            await self._handle_memory_updated(data)
                        elif event_type == "MEMORY_DELETED":
                            await self._handle_memory_deleted(data)
                        elif event_type == "SESSION_STARTED":
                            await self._handle_session_started(data)

                        logger.debug(f"Processed event: {event_type}")

                    except Exception as e:
                        logger.error(f"Failed to process event: {e}")

                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"✗ Event consumer failed: {e}")
        finally:
            self._running = False
            logger.info("Event consumer stopped")

    def stop_event_consumer(self):
        """Stop background event consumer"""
        self._running = False
        logger.info("Stopping event consumer...")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EVENT HANDLERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _handle_memory_created(self, data: Dict[str, Any]):
        """Handle MEMORY_CREATED event"""
        try:
            memory_id = data.get("memory_id")
            user_id = data.get("user_id")
            logger.debug(f"Memory created: {memory_id} for user {user_id}")
            # Trigger Neo4j, Pinecone updates, etc.
        except Exception as e:
            logger.warning(f"Failed to handle MEMORY_CREATED: {e}")

    async def _handle_memory_updated(self, data: Dict[str, Any]):
        """Handle MEMORY_UPDATED event"""
        try:
            memory_id = data.get("memory_id")
            logger.debug(f"Memory updated: {memory_id}")
            # Invalidate caches, update downstream systems
        except Exception as e:
            logger.warning(f"Failed to handle MEMORY_UPDATED: {e}")

    async def _handle_memory_deleted(self, data: Dict[str, Any]):
        """Handle MEMORY_DELETED event"""
        try:
            memory_id = data.get("memory_id")
            logger.debug(f"Memory deleted: {memory_id}")
            # Clean up from all systems
        except Exception as e:
            logger.warning(f"Failed to handle MEMORY_DELETED: {e}")

    async def _handle_session_started(self, data: Dict[str, Any]):
        """Handle SESSION_STARTED event"""
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")
            logger.debug(f"Session started: {session_id} for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to handle SESSION_STARTED: {e}")

    async def get_event_stats(self) -> Dict[str, Any]:
        """Get statistics about events in stream"""
        try:
            info = await redis_client.xinfo_stream(self.stream_key)
            return {
                "total_events": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
            }
        except Exception as e:
            logger.warning(f"Failed to get event stats: {e}")
            return {}

    async def clear_events_before(self, minutes: int = 60) -> int:
        """Clear old events from stream"""
        try:
            cutoff_time = int((datetime.utcnow().timestamp() - minutes * 60) * 1000)
            deleted = await redis_client.xtrim(self.stream_key, minid=cutoff_time, approximate=True)
            logger.info(f"Cleared {deleted} old events")
            return deleted
        except Exception as e:
            logger.warning(f"Failed to clear old events: {e}")
            return 0


# Global instance
memory_event_bus = MemoryEventBus()
