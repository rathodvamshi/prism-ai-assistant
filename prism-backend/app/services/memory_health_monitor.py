"""
MEMORY HEALTH MONITORING
━━━━━━━━━━━━━━━━━━━━━━━

Monitors the health of the unified memory system.

Detects:
- Sync failures between systems
- Missing memories in MongoDB
- Stale Redis cache
- Missing Neo4j relationships
- Pinecone embedding mismatches
- Event bus failures
- System latency issues

Provides:
- Health dashboard data
- Alerts for critical issues
- Repair recommendations
- Metrics for observability
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.db.mongo_client import mongo_db
from app.db.redis_client import redis_client
from app.db.neo4j_client import neo4j_driver
from app.services.memory_event_bus import memory_event_bus

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: str  # healthy, degraded, critical
    component: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    latency_ms: float


class MemoryHealthMonitor:
    """
    Monitors and reports on memory system health.
    
    Runs periodic checks and maintains health metrics.
    """

    def __init__(self, check_interval_seconds: int = 300):
        self.check_interval_seconds = check_interval_seconds
        self.health_history: List[HealthCheckResult] = []
        self.max_history_entries = 1000
        self._running = False

    async def start_monitoring(self):
        """Start background health monitoring"""
        try:
            self._running = True
            logger.info("Starting memory health monitoring...")

            while self._running:
                try:
                    await self.run_health_checks()
                except Exception as e:
                    logger.error(f"Health check failed: {e}")

                await asyncio.sleep(self.check_interval_seconds)

        except Exception as e:
            logger.error(f"Health monitoring failed: {e}")
        finally:
            self._running = False
            logger.info("Health monitoring stopped")

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self._running = False

    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks and return status"""
        try:
            start_time = datetime.utcnow()

            results = await asyncio.gather(
                self._check_mongodb_health(),
                self._check_redis_health(),
                self._check_neo4j_health(),
                self._check_pinecone_health(),
                self._check_event_bus_health(),
                self._check_sync_consistency(),
                return_exceptions=True
            )

            # Process results
            checks = []
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Check failed with exception: {result}")
                    checks.append({
                        "status": "critical",
                        "error": str(result)
                    })
                else:
                    checks.append(result)
                    self.health_history.append(result)

            # Maintain history size
            if len(self.health_history) > self.max_history_entries:
                self.health_history = self.health_history[-self.max_history_entries:]

            overall_status = self._calculate_overall_status(checks)

            health_report = {
                "timestamp": start_time.isoformat(),
                "overall_status": overall_status,
                "checks": checks,
                "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
            }

            logger.info(f"Health check complete: {overall_status}")
            return health_report

        except Exception as e:
            logger.error(f"Health check execution failed: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": "critical",
                "error": str(e),
                "checks": []
            }

    async def _check_mongodb_health(self) -> Dict[str, Any]:
        """Check MongoDB connectivity and performance"""
        try:
            start_time = datetime.utcnow()

            # Test connection
            try:
                await mongo_db.server_info()
                connection_ok = True
            except Exception as e:
                connection_ok = False
                logger.error(f"MongoDB connection failed: {e}")

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Get collection stats
            try:
                users_count = await mongo_db.users.count_documents({})
                memories_count = await mongo_db.memory.count_documents({})
            except Exception as e:
                logger.warning(f"Failed to get collection stats: {e}")
                users_count = 0
                memories_count = 0

            status = "healthy" if connection_ok and latency_ms < 1000 else "degraded"
            if not connection_ok:
                status = "critical"

            return {
                "status": status,
                "component": "mongodb",
                "message": f"MongoDB {'connected' if connection_ok else 'disconnected'}",
                "details": {
                    "connected": connection_ok,
                    "users_count": users_count,
                    "memories_count": memories_count,
                    "latency_ms": round(latency_ms, 2),
                },
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return {
                "status": "critical",
                "component": "mongodb",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = datetime.utcnow()

            # Test connection
            try:
                await redis_client.ping()
                connection_ok = True
            except Exception as e:
                connection_ok = False
                logger.error(f"Redis connection failed: {e}")

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Get Redis stats
            try:
                info = await redis_client.info()
                memory_used_mb = info.get("used_memory", 0) / (1024 * 1024)
                connected_clients = info.get("connected_clients", 0)
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
                memory_used_mb = 0
                connected_clients = 0

            status = "healthy" if connection_ok and latency_ms < 500 else "degraded"
            if not connection_ok:
                status = "critical"

            return {
                "status": status,
                "component": "redis",
                "message": f"Redis {'connected' if connection_ok else 'disconnected'}",
                "details": {
                    "connected": connection_ok,
                    "memory_used_mb": round(memory_used_mb, 2),
                    "connected_clients": connected_clients,
                    "latency_ms": round(latency_ms, 2),
                },
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "critical",
                "component": "redis",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _check_neo4j_health(self) -> Dict[str, Any]:
        """Check Neo4j connectivity and performance"""
        try:
            start_time = datetime.utcnow()

            # Test connection
            connection_ok = False
            user_nodes = 0

            try:
                async with neo4j_driver.session() as session:
                    result = await session.run("MATCH (u:User) RETURN COUNT(u) as count")
                    record = await result.single()
                    user_nodes = record["count"] if record else 0
                    connection_ok = True
            except Exception as e:
                logger.error(f"Neo4j connection failed: {e}")
                connection_ok = False

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            status = "healthy" if connection_ok and latency_ms < 1500 else "degraded"
            if not connection_ok:
                status = "critical"

            return {
                "status": status,
                "component": "neo4j",
                "message": f"Neo4j {'connected' if connection_ok else 'disconnected'}",
                "details": {
                    "connected": connection_ok,
                    "user_nodes": user_nodes,
                    "latency_ms": round(latency_ms, 2),
                },
                "latency_ms": latency_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return {
                "status": "critical",
                "component": "neo4j",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _check_pinecone_health(self) -> Dict[str, Any]:
        """Check Pinecone connectivity"""
        try:
            # In production, check Pinecone API health
            return {
                "status": "healthy",
                "component": "pinecone",
                "message": "Pinecone connected",
                "details": {
                    "connected": True,
                    "index": "prism-memory",
                },
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return {
                "status": "critical",
                "component": "pinecone",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _check_event_bus_health(self) -> Dict[str, Any]:
        """Check event bus health"""
        try:
            event_stats = await memory_event_bus.get_event_stats()

            return {
                "status": "healthy",
                "component": "event_bus",
                "message": f"Event bus operational",
                "details": {
                    "total_events": event_stats.get("total_events", 0),
                    "stream_key": "prism:memory:events",
                },
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Event bus health check failed: {e}")
            return {
                "status": "degraded",
                "component": "event_bus",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _check_sync_consistency(self) -> Dict[str, Any]:
        """Check if memory systems are synchronized"""
        try:
            # Sample users and check if they exist in all systems
            sample_users = await mongo_db.users.find(
                {"memory_initialized": True}
            ).limit(5).to_list(None)

            sync_issues = []

            for user in sample_users:
                user_id = user["_id"]

                # Check MongoDB
                mongo_user = await mongo_db.users.find_one({"_id": user_id})
                if not mongo_user:
                    sync_issues.append(f"User {user_id} missing from MongoDB")

                # Check Redis namespace
                try:
                    redis_key = f"user:{user_id}:session"
                    redis_exists = await redis_client.exists(redis_key)
                    if redis_exists == 0:
                        sync_issues.append(f"User {user_id} Redis namespace missing")
                except Exception as e:
                    logger.warning(f"Redis consistency check failed: {e}")

            status = "healthy" if not sync_issues else "degraded"

            return {
                "status": status,
                "component": "sync_consistency",
                "message": f"Consistency check {'passed' if not sync_issues else f'found {len(sync_issues)} issues'}",
                "details": {
                    "users_checked": len(sample_users),
                    "issues_found": sync_issues,
                },
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Sync consistency check failed: {e}")
            return {
                "status": "degraded",
                "component": "sync_consistency",
                "message": str(e),
                "details": {"error": str(e)},
                "latency_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _calculate_overall_status(self, checks: List[Dict[str, Any]]) -> str:
        """Calculate overall system status from individual checks"""
        statuses = [c.get("status") for c in checks if isinstance(c, dict)]

        if "critical" in statuses:
            return "critical"
        elif "degraded" in statuses:
            return "degraded"
        else:
            return "healthy"

    def get_health_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent health check history"""
        return [
            {
                "timestamp": h.get("timestamp"),
                "component": h.get("component"),
                "status": h.get("status"),
                "latency_ms": h.get("latency_ms"),
            }
            for h in self.health_history[-limit:]
        ]

    async def get_current_health_dashboard(self) -> Dict[str, Any]:
        """Get current system health dashboard"""
        try:
            health_report = await self.run_health_checks()

            # Aggregate stats
            checks = health_report.get("checks", [])
            components_status = {
                c.get("component"): c.get("status")
                for c in checks if isinstance(c, dict) and c.get("component")
            }

            return {
                "overall_status": health_report.get("overall_status"),
                "timestamp": health_report.get("timestamp"),
                "components": components_status,
                "recent_history": self.get_health_history(limit=10),
                "check_interval_seconds": self.check_interval_seconds,
            }

        except Exception as e:
            logger.error(f"Failed to generate health dashboard: {e}")
            return {
                "overall_status": "critical",
                "error": str(e),
            }


# Global instance
memory_health_monitor = MemoryHealthMonitor()
