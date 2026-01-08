import json
import asyncio
import structlog
from typing import Dict, Any, Optional, Callable
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger()


class RedisService:
    """Service for Redis message queue operations."""

    def __init__(self, redis_url: str):
        """
        Initialize Redis service.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.pubsub = None
        self.listener_task = None

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis", url=self.redis_url)
        except RedisError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        if self.pubsub:
            await self.pubsub.close()

        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def publish_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Publish a task to the worker queue.

        Args:
            task_data: Task data to send to worker

        Returns:
            True if published successfully
        """
        try:
            task_json = json.dumps(task_data)
            await self.redis.lpush("adw:tasks", task_json)
            logger.info("Published task to queue", task_id=task_data.get("task_id"))
            return True
        except Exception as e:
            logger.error("Failed to publish task", error=str(e))
            return False

    async def start_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        """
        Start listening for worker responses.

        Args:
            callback: Async function to call when message received
        """
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe("adw:responses")
            logger.info("Started listening for worker responses")

            self.listener_task = asyncio.create_task(
                self._listen_loop(callback)
            )
        except Exception as e:
            logger.error("Failed to start listener", error=str(e))
            raise

    async def _listen_loop(self, callback: Callable[[Dict[str, Any]], Any]):
        """
        Internal loop for listening to messages.

        Args:
            callback: Function to call with received messages
        """
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        logger.info("Received worker response", data=data)
                        await callback(data)
                    except json.JSONDecodeError as e:
                        logger.error("Failed to decode message", error=str(e))
                    except Exception as e:
                        logger.error("Error processing message", error=str(e))
        except asyncio.CancelledError:
            logger.info("Listener loop cancelled")
            raise
        except Exception as e:
            logger.error("Listener loop error", error=str(e))
