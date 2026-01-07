import structlog
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from bot.models.user import User
from bot.models.conversation import Conversation
from bot.models.message import Message

logger = structlog.get_logger()


class MongoDB:
    """MongoDB connection manager."""

    client: AsyncIOMotorClient = None
    database = None

    @classmethod
    async def connect(cls, mongodb_uri: str, database_name: str = "hermes_bot"):
        """
        Initialize MongoDB connection and Beanie ODM.

        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name (extracted from URI or default)
        """
        try:
            logger.info("Connecting to MongoDB...", uri=mongodb_uri.split("@")[-1])
            cls.client = AsyncIOMotorClient(mongodb_uri)
            cls.database = cls.client[database_name]

            # Initialize Beanie with document models
            await init_beanie(
                database=cls.database,
                document_models=[User, Conversation, Message],
            )

            logger.info("Successfully connected to MongoDB", database=database_name)
        except Exception as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            raise

    @classmethod
    async def close(cls):
        """Close MongoDB connection."""
        if cls.client:
            logger.info("Closing MongoDB connection...")
            cls.client.close()
            logger.info("MongoDB connection closed")
