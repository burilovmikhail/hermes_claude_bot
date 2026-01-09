"""Utility functions for ADW system."""

import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, Type, Union, Optional

T = TypeVar('T')


def make_adw_id() -> str:
    """Generate a short 8-character UUID for ADW tracking."""
    return str(uuid.uuid4())[:8]


def setup_logger(adw_id: str, trigger_type: str = "adw_plan_build") -> logging.Logger:
    """Set up logger that writes to both console and file using adw_id.
    
    Args:
        adw_id: The ADW workflow ID
        trigger_type: Type of trigger (adw_plan_build, trigger_webhook, etc.)
    
    Returns:
        Configured logger instance
    """
    # Create log directory: agents/{adw_id}/adw_plan_build/
    # __file__ is in adws/adw_modules/, so we need to go up 3 levels to get to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "agents", adw_id, trigger_type)
    os.makedirs(log_dir, exist_ok=True)
    
    # Log file path: agents/{adw_id}/adw_plan_build/execution.log
    log_file = os.path.join(log_dir, "execution.log")
    
    # Create logger with unique name using adw_id
    logger = logging.getLogger(f"adw_{adw_id}")
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File handler - captures everything
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler - INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Format with timestamp for file
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Simpler format for console (similar to current print statements)
    console_formatter = logging.Formatter('%(message)s')
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log initial setup message
    logger.info(f"ADW Logger initialized - ID: {adw_id}")
    logger.debug(f"Log file: {log_file}")
    
    return logger


def get_logger(adw_id: str) -> logging.Logger:
    """Get existing logger by ADW ID.
    
    Args:
        adw_id: The ADW workflow ID
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"adw_{adw_id}")


def parse_json(text: str, target_type: Type[T] = None) -> Union[T, Any]:
    """Parse JSON that may be wrapped in markdown code blocks.
    
    Handles various formats:
    - Raw JSON
    - JSON wrapped in ```json ... ```
    - JSON wrapped in ``` ... ```
    - JSON with extra whitespace or newlines
    
    Args:
        text: String containing JSON, possibly wrapped in markdown
        target_type: Optional type to validate/parse the result into (e.g., List[TestResult])
        
    Returns:
        Parsed JSON object, optionally validated as target_type
        
    Raises:
        ValueError: If JSON cannot be parsed from the text
    """
    # Try to extract JSON from markdown code blocks
    # Pattern matches ```json\n...\n``` or ```\n...\n```
    code_block_pattern = r'```(?:json)?\s*\n(.*?)\n```'
    match = re.search(code_block_pattern, text, re.DOTALL)
    
    if match:
        json_str = match.group(1).strip()
    else:
        # No code block found, try to parse the entire text
        json_str = text.strip()
    
    # Try to find JSON array or object boundaries if not already clean
    if not (json_str.startswith('[') or json_str.startswith('{')):
        # Look for JSON array
        array_start = json_str.find('[')
        array_end = json_str.rfind(']')
        
        # Look for JSON object
        obj_start = json_str.find('{')
        obj_end = json_str.rfind('}')
        
        # Determine which comes first and extract accordingly
        if array_start != -1 and (obj_start == -1 or array_start < obj_start):
            if array_end != -1:
                json_str = json_str[array_start:array_end + 1]
        elif obj_start != -1:
            if obj_end != -1:
                json_str = json_str[obj_start:obj_end + 1]
    
    try:
        result = json.loads(json_str)
        
        # If target_type is provided and has from_dict/parse_obj/model_validate methods (Pydantic)
        if target_type and hasattr(target_type, '__origin__'):
            # Handle List[SomeType] case
            if target_type.__origin__ == list:
                item_type = target_type.__args__[0]
                # Try Pydantic v2 first, then v1
                if hasattr(item_type, 'model_validate'):
                    result = [item_type.model_validate(item) for item in result]
                elif hasattr(item_type, 'parse_obj'):
                    result = [item_type.parse_obj(item) for item in result]
        elif target_type:
            # Handle single Pydantic model
            if hasattr(target_type, 'model_validate'):
                result = target_type.model_validate(result)
            elif hasattr(target_type, 'parse_obj'):
                result = target_type.parse_obj(result)
            
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}. Text was: {json_str[:200]}...")


def load_task_input(task_id: Optional[str] = None, logger: Optional[logging.Logger] = None) -> dict:
    """
    Load task input from task_input.json file.

    This function looks for task_input.json in the adws directory of the current repository.
    The file is created by the Hermes worker before executing ADW workflows.

    Args:
        task_id: Optional task ID for validation (not currently used)
        logger: Optional logger for debug messages

    Returns:
        Dictionary containing task input data with keys:
        - task_id: Unique task ID
        - source: "jira" or "plain_text"
        - jira_ticket: Optional Jira ticket key
        - jira_details: Optional Jira ticket details
        - title: Task title
        - description: Task description
        - telegram_id: User's Telegram ID

    Raises:
        FileNotFoundError: If task_input.json is not found
        ValueError: If task_input.json is invalid JSON
    """
    # Get the ADW scripts directory (where this utils.py file is located)
    adws_dir = Path(__file__).parent.parent
    task_input_path = adws_dir / "task_input.json"

    if not task_input_path.exists():
        error_msg = f"Task input file not found: {task_input_path}"
        if logger:
            logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with open(task_input_path, "r") as f:
            task_input = json.load(f)

        if logger:
            logger.info(f"Loaded task input from {task_input_path}")
            logger.debug(f"Task input: {json.dumps(task_input, indent=2)}")

        # Validate required fields
        required_fields = ["task_id", "source", "title", "description"]
        missing_fields = [field for field in required_fields if field not in task_input]

        if missing_fields:
            error_msg = f"Task input missing required fields: {missing_fields}"
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)

        return task_input

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse task_input.json: {e}"
        if logger:
            logger.error(error_msg)
        raise ValueError(error_msg)


def create_task_input_from_jira(
    task_id: str,
    jira_ticket: str,
    jira_details: dict,
    telegram_id: int
) -> dict:
    """
    Create task input dictionary from Jira ticket details.

    Args:
        task_id: Unique task ID
        jira_ticket: Jira ticket key (e.g., "MS-1234")
        jira_details: Jira ticket details from Jira service
        telegram_id: User's Telegram ID

    Returns:
        Task input dictionary
    """
    return {
        "task_id": task_id,
        "source": "jira",
        "jira_ticket": jira_ticket,
        "jira_details": jira_details,
        "title": jira_details.get("summary", "Task"),
        "description": jira_details.get("description", ""),
        "telegram_id": telegram_id
    }


def create_task_input_from_text(
    task_id: str,
    task_description: str,
    telegram_id: int
) -> dict:
    """
    Create task input dictionary from plain text description.

    Args:
        task_id: Unique task ID
        task_description: Task description text
        telegram_id: User's Telegram ID

    Returns:
        Task input dictionary
    """
    # Extract first line or first 50 chars as title
    title = task_description.split("\n")[0][:50]

    return {
        "task_id": task_id,
        "source": "plain_text",
        "jira_ticket": None,
        "jira_details": None,
        "title": title,
        "description": task_description,
        "telegram_id": telegram_id
    }