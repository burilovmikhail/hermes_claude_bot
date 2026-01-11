import asyncio
import json
import os
import subprocess
import structlog
import shutil
from pathlib import Path
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import settings
from reporting import MessageFilter, MessageCategory, ReportingLevel
from adws.adw_modules.agent import prompt_claude_code
from adws.adw_modules.data_types import AgentPromptRequest, AgentPromptResponse

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

    async def send_status(
        self,
        task_id: str,
        telegram_id: int,
        status: str,
        message: str,
        reporting_level: ReportingLevel = "basic",
        category: MessageCategory = None
    ):
        """
        Send status update to bot via Redis with message filtering.

        Args:
            task_id: Task identifier
            telegram_id: User's Telegram ID
            status: Status (started, progress, finished, failed)
            message: Status message
            reporting_level: Reporting verbosity level
            category: Message category (auto-detected if None)
        """
        try:
            # Auto-categorize message if category not provided
            if category is None:
                category = MessageFilter.categorize_message(message)

            # Filter progress and started messages based on reporting level
            # Always send finished and failed status messages
            if status in ("progress", "started"):
                if not MessageFilter.should_send_message(message, reporting_level, category):
                    logger.debug(
                        "Filtered message",
                        task_id=task_id,
                        category=category,
                        reporting_level=reporting_level
                    )
                    return

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
        if operation == "git_add":
            await self.handle_git_add(task_data)
        elif operation == "git_remove":
            await self.handle_git_remove(task_data)
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
        workflow_name = task_data.get("workflow_name", "plan_build")
        repo_url = task_data.get("repo_url")
        task_description = task_data.get("task_description")
        jira_ticket = task_data.get("jira_ticket")
        jira_details = task_data.get("jira_details")
        reporting_level = task_data.get("reporting_level", "basic")

        logger.info("Processing ADW task", task_id=task_id, workflow=workflow_name, reporting_level=reporting_level)

        try:
            # Send started status
            await self.send_status(
                task_id,
                telegram_id,
                "started",
                f"Starting workflow: {workflow_name}",
                reporting_level
            )

            # Prepare workspace for this task (use telegram_id subdirectory)
            user_workspace = self.workspace / str(telegram_id)
            user_workspace.mkdir(parents=True, exist_ok=True)

            # Determine repository directory name
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            repo_dir = user_workspace / repo_name

            # Clone or update repository
            repo_dir = await self.setup_repository(
                repo_url,
                user_workspace,
                task_id,
                telegram_id,
                reporting_level
            )

            await self.send_status(
                task_id,
                telegram_id,
                "progress",
                "Repository setup complete. Copying ADW scripts...",
                reporting_level,
                "technical"
            )

            # Copy ADW scripts to target repository
            await self.copy_adw_scripts(repo_dir, task_id, telegram_id, reporting_level)

            # Prepare task input file
            await self.prepare_task_input(
                repo_dir,
                task_id,
                task_description,
                jira_ticket,
                jira_details,
                telegram_id
            )

            await self.send_status(
                task_id,
                telegram_id,
                "progress",
                f"Running ADW workflow: {workflow_name}...",
                reporting_level,
                "workflow"
            )

            # Execute ADW workflow
            await self.execute_adw_workflow(
                repo_dir,
                task_id,
                workflow_name,
                telegram_id,
                reporting_level
            )

            # Send finished status
            await self.send_status(
                task_id,
                telegram_id,
                "finished",
                f"✅ Workflow completed successfully!\n\nRepository: {repo_url}\nWorkspace: {repo_dir}",
                reporting_level
            )

            logger.info("Task completed", task_id=task_id)

        except Exception as e:
            logger.error("Task failed", task_id=task_id, error=str(e))
            await self.send_status(
                task_id,
                telegram_id,
                "failed",
                f"❌ Workflow failed: {str(e)}",
                reporting_level
            )

    async def copy_adw_scripts(
        self,
        repo_dir: Path,
        task_id: str,
        telegram_id: int,
        reporting_level: ReportingLevel = "basic"
    ):
        """
        Copy ADW scripts from Hermes to target repository and install dependencies.

        Args:
            repo_dir: Target repository directory
            task_id: Task identifier
            telegram_id: User's Telegram ID
            reporting_level: Reporting verbosity level
        """
        try:
            # Get the ADW scripts directory
            # In Docker: /app/adws (copied during build)
            # In development: ../adws relative to worker directory
            worker_dir = Path(__file__).parent

            # Try Docker location first
            adws_source = worker_dir / "adws"

            # If not found, try development location (parent directory)
            if not adws_source.exists():
                adws_source = worker_dir.parent / "adws"

            if not adws_source.exists():
                raise FileNotFoundError(f"ADW scripts not found at: {adws_source}")

            # Target ADW directory in repository
            adws_target = repo_dir / "adws"

            # Remove existing ADW directory if present
            if adws_target.exists():
                shutil.rmtree(adws_target)

            # Copy ADW scripts
            shutil.copytree(adws_source, adws_target)

            logger.info("Copied ADW scripts", source=str(adws_source), target=str(adws_target))

            # Install ADW dependencies in the target repository
            adw_requirements = adws_target / "requirements.txt"
            if adw_requirements.exists():
                logger.info("Installing ADW dependencies")
                result = subprocess.run(
                    ["pip", "install", "-q", "-r", str(adw_requirements)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.warning(f"Failed to install ADW dependencies: {result.stderr}")
                    # Don't raise - dependencies might already be installed
                else:
                    logger.info("ADW dependencies installed successfully")

        except Exception as e:
            logger.error("Failed to copy ADW scripts", error=str(e))
            raise

    async def prepare_task_input(
        self,
        repo_dir: Path,
        task_id: str,
        task_description: str,
        jira_ticket: str | None,
        jira_details: dict | None,
        telegram_id: int
    ):
        """
        Prepare task input file for ADW workflow.

        Creates a JSON file with task details that will be read by ADW scripts.

        Args:
            repo_dir: Target repository directory
            task_id: Task identifier
            task_description: Task description text
            jira_ticket: Optional Jira ticket key
            jira_details: Optional Jira ticket details
            telegram_id: User's Telegram ID
        """
        try:
            # Determine task title
            if jira_details:
                task_title = jira_details.get("summary", "Task")
            else:
                # Extract first line or first 50 chars as title
                task_title = task_description.split("\n")[0][:50]

            # Prepare task input data
            task_input = {
                "task_id": task_id,
                "source": "jira" if jira_ticket else "plain_text",
                "jira_ticket": jira_ticket,
                "jira_details": jira_details,
                "title": task_title,
                "description": task_description,
                "telegram_id": telegram_id
            }

            # Write task input file
            task_input_file = repo_dir / "adws" / "task_input.json"
            with open(task_input_file, "w") as f:
                json.dump(task_input, f, indent=2)

            logger.info("Prepared task input", file=str(task_input_file))

        except Exception as e:
            logger.error("Failed to prepare task input", error=str(e))
            raise

    async def execute_adw_workflow(
        self,
        repo_dir: Path,
        task_id: str,
        workflow_name: str,
        telegram_id: int,
        reporting_level: ReportingLevel = "basic"
    ):
        """
        Execute ADW workflow script.

        Args:
            repo_dir: Target repository directory
            task_id: Task identifier
            workflow_name: Workflow name (e.g., "plan_build", "plan_build_test")
            telegram_id: User's Telegram ID
            reporting_level: Reporting verbosity level
        """
        try:
            # Map workflow name to script
            workflow_script_map = {
                "plan": "adw_plan.py",
                "build": "adw_build.py",
                "plan_build": "adw_plan_build.py",
                "plan_build_test": "adw_plan_build.py",  # Will add test support later
            }

            script_name = workflow_script_map.get(workflow_name, "adw_plan_build.py")
            script_path = repo_dir / "adws" / script_name

            if not script_path.exists():
                raise FileNotFoundError(f"Workflow script not found: {script_path}")

            # Execute the workflow script
            # Pass task_id as argument (scripts will read task_input.json)
            cmd = ["python", str(script_path), task_id]

            logger.info("Executing ADW workflow", script=script_name, cwd=str(repo_dir))

            # Send progress update
            await self.send_status(
                task_id,
                telegram_id,
                "progress",
                f"Executing {workflow_name} workflow...",
                reporting_level,
                "workflow"
            )

            # Run the workflow (this will take time)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ}
            )

            # Stream output and send progress updates
            async def read_stream(stream, is_stderr=False):
                """Read stream and log output."""
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode().strip()
                    if text:
                        if is_stderr:
                            logger.error("ADW stderr", line=text)
                        else:
                            logger.info("ADW stdout", line=text)

                        # Send progress for important lines
                        if any(keyword in text.lower() for keyword in ["error", "failed", "completed", "created"]):
                            await self.send_status(
                                task_id,
                                telegram_id,
                                "progress",
                                text[:200],  # Limit message length
                                reporting_level
                            )

            # Read both streams concurrently
            await asyncio.gather(
                read_stream(process.stdout, False),
                read_stream(process.stderr, True)
            )

            # Wait for process to complete
            return_code = await process.wait()

            if return_code != 0:
                raise Exception(f"Workflow script failed with exit code {return_code}")

            logger.info("ADW workflow completed successfully", task_id=task_id)

        except Exception as e:
            logger.error("Failed to execute ADW workflow", error=str(e))
            raise

    async def setup_repository(
        self,
        github_repo: str,
        task_workspace: Path,
        task_id: str,
        telegram_id: int,
        reporting_level: ReportingLevel = "basic"
    ) -> Path:
        """
        Clone or update a GitHub repository.

        Args:
            github_repo: Repository in format "owner/repo"
            task_workspace: Task workspace directory
            task_id: Task identifier
            telegram_id: User's Telegram ID
            reporting_level: Reporting verbosity level

        Returns:
            Path to repository directory
        """
        repo_dir = task_workspace / github_repo.split("/")[-1]

        try:
            if repo_dir.exists():
                # Repository already exists, switch to main branch and pull latest
                logger.info("Updating repository", repo=github_repo)
                await self.send_status(
                    task_id,
                    telegram_id,
                    "progress",
                    f"Updating repository: {github_repo}",
                    reporting_level,
                    "technical"
                )

                try:
                    # Switch to main branch first
                    logger.info("Switching to main branch", repo=github_repo)
                    await self.send_status(
                        task_id,
                        telegram_id,
                        "progress",
                        f"Switching to main branch: {github_repo}",
                        reporting_level,
                        "technical"
                    )

                    checkout_result = subprocess.run(
                        ["git", "checkout", "main"],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if checkout_result.returncode != 0:
                        raise Exception(f"Git checkout failed: {checkout_result.stderr}")

                    # Pull latest changes
                    pull_result = subprocess.run(
                        ["git", "pull"],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if pull_result.returncode != 0:
                        raise Exception(f"Git pull failed: {pull_result.stderr}")

                except Exception as git_error:
                    # Git operations failed, remove directory and re-clone
                    logger.warning(
                        "Git operations failed, removing and re-cloning",
                        repo=github_repo,
                        error=str(git_error)
                    )
                    await self.send_status(
                        task_id,
                        telegram_id,
                        "progress",
                        f"Recovering repository: {github_repo}",
                        reporting_level,
                        "technical"
                    )

                    shutil.rmtree(repo_dir)

                    # Fall through to clone logic below
                    logger.info("Cloning repository after recovery", repo=github_repo)
                    await self.send_status(
                        task_id,
                        telegram_id,
                        "progress",
                        f"Cloning repository: {github_repo}",
                        reporting_level,
                        "technical"
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
            else:
                # Clone repository
                logger.info("Cloning repository", repo=github_repo)
                await self.send_status(
                    task_id,
                    telegram_id,
                    "progress",
                    f"Cloning repository: {github_repo}",
                    reporting_level,
                    "technical"
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

    async def handle_git_add(self, task_data: dict):
        """
        Handle git add operation (clone + prime).

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        telegram_id = task_data.get("telegram_id")
        short_name = task_data.get("short_name")
        repo_url = task_data.get("repo_url")
        full_url = task_data.get("full_url")
        repo_id = task_data.get("repo_id")

        logger.info("Adding repository (clone + prime)", task_id=task_id, repo_url=repo_url)

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
                    "git_add",
                    repo_id
                )
                return

            # Clone repository with authentication
            clone_url = full_url.replace(
                "https://github.com/",
                f"https://{settings.github_token}@github.com/"
            )

            logger.info("Cloning repository", repo_url=repo_url)
            result = subprocess.run(
                ["git", "clone", clone_url, str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Clone failed"
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Clone failed: {error_msg}",
                    "git_add",
                    repo_id
                )
                logger.error("Clone failed", error=error_msg)
                return

            logger.info("Repository cloned successfully, running /prime", repo_url=repo_url)

            # Run Claude Code with /prime command using agent module
            try:
                # Create output directory for prime JSONL files
                prime_dir = repo_dir / "prime"
                prime_dir.mkdir(exist_ok=True)
                output_file = str(prime_dir / "prime_output.jsonl")

                # Build AgentPromptRequest
                request = AgentPromptRequest(
                    prompt="/prime",
                    adw_id=task_id,
                    agent_name="git_prime",
                    model="sonnet",
                    dangerously_skip_permissions=True,
                    output_file=output_file
                )

                logger.info("Running prime with agent module", output_file=output_file)

                # Change to repository directory and run prime
                original_cwd = os.getcwd()
                os.chdir(str(repo_dir))

                try:
                    response = prompt_claude_code(request)
                finally:
                    os.chdir(original_cwd)

                # Handle response
                if response.success:
                    prime_output = response.output
                    await self.send_git_response(
                        task_id,
                        telegram_id,
                        "success",
                        f"Repository added and primed successfully: {short_name}",
                        "git_add",
                        repo_id,
                        prime_output
                    )
                    logger.info("Repository primed successfully", repo_url=repo_url, session_id=response.session_id)
                else:
                    error_msg = response.output or "Prime failed"
                    await self.send_git_response(
                        task_id,
                        telegram_id,
                        "failed",
                        f"Repository cloned but prime failed: {error_msg}",
                        "git_add",
                        repo_id
                    )
                    logger.error("Prime failed", error=error_msg)

            except Exception as e:
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "failed",
                    f"Repository cloned but prime operation failed: {str(e)}",
                    "git_add",
                    repo_id
                )
                logger.error("Prime exception", repo_url=repo_url, error=str(e))

        except subprocess.TimeoutExpired:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                "Clone operation timed out",
                "git_add",
                repo_id
            )
            logger.error("Clone timeout", repo_url=repo_url)
        except Exception as e:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                f"Add operation error: {str(e)}",
                "git_add",
                repo_id
            )
            logger.error("Add error", error=str(e))


    async def handle_git_remove(self, task_data: dict):
        """
        Handle git remove operation (delete repository directory).

        Args:
            task_data: Task data from Redis queue
        """
        task_id = task_data.get("task_id")
        telegram_id = task_data.get("telegram_id")
        short_name = task_data.get("short_name")
        repo_id = task_data.get("repo_id")

        logger.info("Removing repository", task_id=task_id, short_name=short_name)

        try:
            # Construct repository directory path
            repo_dir = self.workspace / str(telegram_id) / short_name

            # Check if directory exists
            if repo_dir.exists():
                logger.info("Removing repository directory", path=repo_dir)

                # Remove directory recursively
                shutil.rmtree(repo_dir)

                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "success",
                    f"Repository '{short_name}' removed successfully (database and filesystem)",
                    "git_remove",
                    repo_id
                )
                logger.info("Repository removed successfully", short_name=short_name)
            else:
                # Directory doesn't exist, but that's okay
                logger.warning("Repository directory not found, already cleaned up", path=repo_dir)
                await self.send_git_response(
                    task_id,
                    telegram_id,
                    "success",
                    f"Repository '{short_name}' removed from database (directory was already cleaned up)",
                    "git_remove",
                    repo_id
                )

        except PermissionError as e:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                f"Permission denied while removing '{short_name}': {str(e)}",
                "git_remove",
                repo_id
            )
            logger.error("Permission error removing repository", short_name=short_name, error=str(e))
        except Exception as e:
            await self.send_git_response(
                task_id,
                telegram_id,
                "failed",
                f"Failed to remove '{short_name}': {str(e)}",
                "git_remove",
                repo_id
            )
            logger.error("Error removing repository", short_name=short_name, error=str(e))

    async def send_git_response(
        self,
        task_id: str,
        telegram_id: int,
        status: str,
        message: str,
        operation: str,
        repo_id: str,
        prime_output: str = None
    ):
        """
        Send git operation response to bot via Redis.

        Args:
            task_id: Task identifier
            telegram_id: User's Telegram ID
            status: Status (success, failed)
            message: Status message
            operation: Operation type (git_add)
            repo_id: Repository ID in MongoDB
            prime_output: Optional output from /prime command
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
            if prime_output is not None:
                response["prime_output"] = prime_output
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
