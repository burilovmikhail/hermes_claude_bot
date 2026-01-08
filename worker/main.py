import asyncio
import json
import os
import subprocess
import structlog
from pathlib import Path
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import settings

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


class WorkerService:
    """Worker service that processes ADW tasks."""

    def __init__(self):
        self.redis: Redis = None
        self.running = False
        self.workspace = Path(settings.workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis", url=settings.redis_url)
        except RedisError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def send_status(self, task_id: str, telegram_id: int, status: str, message: str):
        """
        Send status update to bot via Redis.

        Args:
            task_id: Task identifier
            telegram_id: User's Telegram ID
            status: Status (started, progress, finished, failed)
            message: Status message
        """
        try:
            response = {
                "task_id": task_id,
                "telegram_id": telegram_id,
                "status": status,
                "message": message
            }
            await self.redis.publish("adw:responses", json.dumps(response))
            logger.info("Sent status update", task_id=task_id, status=status)
        except Exception as e:
            logger.error("Failed to send status update", task_id=task_id, error=str(e))

    async def process_task(self, task_data: dict):
        """
        Process a task from Redis queue.

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        operation = task_data.get("operation", "adw")

        logger.info("Processing task", task_id=task_id, operation=operation)

        # Route to appropriate handler
        if operation == "git_clone":
            await self.handle_git_clone(task_data)
        elif operation == "git_pull":
            await self.handle_git_pull(task_data)
        else:
            await self.handle_adw_task(task_data)

    async def handle_adw_task(self, task_data: dict):
        """
        Process an ADW (AI-Driven Workflow) task.

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        telegram_id = task_data.get("telegram_id")
        workflow_name = task_data.get("workflow_name", "plan_build_test")
        github_repo = task_data.get("github_repo")
        task_description = task_data.get("task_description")
        jira_details = task_data.get("jira_details")

        logger.info("Processing ADW task", task_id=task_id, workflow=workflow_name)

        try:
            # Send started status
            await self.send_status(
                task_id,
                telegram_id,
                "started",
                f"Starting workflow: {workflow_name}"
            )

            # Prepare workspace for this task
            task_workspace = self.workspace / task_id
            task_workspace.mkdir(parents=True, exist_ok=True)

            # Clone or update repository if specified
            if github_repo:
                repo_dir = await self.setup_repository(
                    github_repo,
                    task_workspace,
                    task_id,
                    telegram_id
                )
            else:
                repo_dir = task_workspace

            # TODO: Run Claude Code workflow
            # For now, just simulate workflow execution
            await self.send_status(
                task_id,
                telegram_id,
                "progress",
                "Repository setup complete. Running workflow..."
            )

            # Placeholder for Claude Code execution
            # In a real implementation, you would:
            # 1. Install claude-code if not already installed
            # 2. Prepare the prompt with task description and Jira details
            # 3. Execute: claude-code --prompt "..." --workspace repo_dir
            # 4. Stream output and send progress updates

            await asyncio.sleep(2)  # Simulate work

            # Send finished status
            await self.send_status(
                task_id,
                telegram_id,
                "finished",
                f"Workflow completed successfully!\n\nWorkspace: {repo_dir}"
            )

            logger.info("Task completed", task_id=task_id)

        except Exception as e:
            logger.error("Task failed", task_id=task_id, error=str(e))
            await self.send_status(
                task_id,
                telegram_id,
                "failed",
                f"Workflow failed: {str(e)}"
            )

    async def setup_repository(
        self,
        github_repo: str,
        task_workspace: Path,
        task_id: str,
        telegram_id: int
    ) -> Path:
        """
        Clone or update a GitHub repository.

        Args:
            github_repo: Repository in format "owner/repo"
            task_workspace: Task workspace directory
            task_id: Task identifier
            telegram_id: User's Telegram ID

        Returns:
            Path to repository directory
        """
        repo_dir = task_workspace / github_repo.split("/")[-1]

        try:
            if repo_dir.exists():
                # Repository already exists, pull latest
                logger.info("Updating repository", repo=github_repo)
                await self.send_status(
                    task_id,
                    telegram_id,
                    "progress",
                    f"Updating repository: {github_repo}"
                )

                result = subprocess.run(
                    ["git", "pull"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    raise Exception(f"Git pull failed: {result.stderr}")
            else:
                # Clone repository
                logger.info("Cloning repository", repo=github_repo)
                await self.send_status(
                    task_id,
                    telegram_id,
                    "progress",
                    f"Cloning repository: {github_repo}"
                )

                # Prepare git URL with token
                repo_url = f"https://{settings.github_token}@github.com/{github_repo}.git"

                result = subprocess.run(
                    ["git", "clone", repo_url, str(repo_dir)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode != 0:
                    raise Exception(f"Git clone failed: {result.stderr}")

            logger.info("Repository ready", repo=github_repo, path=repo_dir)
            return repo_dir

        except Exception as e:
            logger.error("Failed to setup repository", repo=github_repo, error=str(e))
            raise

    async def handle_git_clone(self, task_data: dict):
        """
        Handle git clone operation.

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        telegram_id = task_data.get("telegram_id")
        short_name = task_data.get("short_name")
        repo_url = task_data.get("repo_url")
        full_url = task_data.get("full_url")
        repo_id = task_data.get("repo_id")

        logger.info("Cloning repository", task_id=task_id, repo_url=repo_url)

        try:
            # Create directory for this repository using short_name
            repo_dir = self.workspace / f"{telegram_id}" / short_name
            repo_dir.parent.mkdir(parents=True, exist_ok=True)

            if repo_dir.exists():
                # Repository directory already exists
                logger.warning("Repository directory already exists", path=repo_dir)
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Repository directory '{short_name}' already exists",
                    "git_clone",
                    repo_id
                )
                return

            # Clone repository with authentication
            clone_url = full_url.replace(
                "https://github.com/",
                f"https://{settings.github_token}@github.com/"
            )

            result = subprocess.run(
                ["git", "clone", clone_url, str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "success",
                    f"Repository cloned successfully: {short_name}",
                    "git_clone",
                    repo_id
                )
                logger.info("Repository cloned successfully", repo_url=repo_url)
            else:
                error_msg = result.stderr or "Clone failed"
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Clone failed: {error_msg}",
                    "git_clone",
                    repo_id
                )
                logger.error("Clone failed", error=error_msg)

        except subprocess.TimeoutExpired:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                "Clone operation timed out",
                "git_clone",
                repo_id
            )
            logger.error("Clone timeout", repo_url=repo_url)
        except Exception as e:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                f"Clone error: {str(e)}",
                "git_clone",
                repo_id
            )
            logger.error("Clone error", error=str(e))

    async def handle_git_pull(self, task_data: dict):
        """
        Handle git pull operation.

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        telegram_id = task_data.get("telegram_id")
        short_name = task_data.get("short_name")
        repo_url = task_data.get("repo_url")
        repo_id = task_data.get("repo_id")

        logger.info("Pulling repository", task_id=task_id, repo_url=repo_url)

        try:
            # Find repository directory
            repo_dir = self.workspace / f"{telegram_id}" / short_name

            if not repo_dir.exists():
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Repository '{short_name}' not found. Use /git clone first.",
                    "git_pull",
                    repo_id
                )
                return

            # Pull latest changes
            result = subprocess.run(
                ["git", "pull"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if "Already up to date" in output:
                    message = f"Repository '{short_name}' is already up to date"
                else:
                    message = f"Repository '{short_name}' pulled successfully"

                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "success",
                    message,
                    "git_pull",
                    repo_id
                )
                logger.info("Repository pulled successfully", repo_url=repo_url)
            else:
                error_msg = result.stderr or "Pull failed"
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Pull failed: {error_msg}",
                    "git_pull",
                    repo_id
                )
                logger.error("Pull failed", error=error_msg)

        except subprocess.TimeoutExpired:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                "Pull operation timed out",
                "git_pull",
                repo_id
            )
            logger.error("Pull timeout", repo_url=repo_url)
        except Exception as e:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                f"Pull error: {str(e)}",
                "git_pull",
                repo_id
            )
            logger.error("Pull error", error=str(e))

    async def send_git_response(
        self,
        task_id: str,
        telegram_id: int,
        status: str,
        message: str,
        operation: str,
        repo_id: str
    ):
        """
        Send git operation response to bot via Redis.

        Args:
            task_id: Task identifier
            telegram_id: User's Telegram ID
            status: Status (success, failed)
            message: Status message
            operation: Operation type (git_clone, git_pull)
            repo_id: Repository ID in MongoDB
        """
        try:
            response = {
                "task_id": task_id,
                "telegram_id": telegram_id,
                "status": status,
                "message": message,
                "operation": operation,
                "repo_id": repo_id
            }
            await self.redis.publish("adw:responses", json.dumps(response))
            logger.info("Sent git response", task_id=task_id, status=status)
        except Exception as e:
            logger.error("Failed to send git response", task_id=task_id, error=str(e))

    async def run(self):
        """Main worker loop - process tasks from Redis queue."""
        self.running = True
        logger.info("Worker started, waiting for tasks...")

        while self.running:
            try:
                # Block and wait for task from queue (timeout 1 second)
                result = await self.redis.brpop("adw:tasks", timeout=1)

                if result:
                    _, task_json = result
                    task_data = json.loads(task_json)
                    logger.info("Received task", task_id=task_data.get("task_id"))

                    # Process task
                    await self.process_task(task_data)

            except json.JSONDecodeError as e:
                logger.error("Failed to decode task", error=str(e))
            except Exception as e:
                logger.error("Error in worker loop", error=str(e))
                await asyncio.sleep(1)

    def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Worker stopping...")


async def main():
    """Main entry point for worker service."""
    worker = WorkerService()

    try:
        await worker.connect()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        raise
    finally:
        await worker.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
