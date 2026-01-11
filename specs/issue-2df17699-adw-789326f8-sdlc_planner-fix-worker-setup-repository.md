# Bug: Fix Worker Setup Repository Branch and Error Handling

## Bug Description
The `setup_repository` function in `worker/main.py` has a critical flaw in its repository update logic. When a repository already exists locally from a previous execution, the function attempts to pull changes directly without checking or switching to the main branch. This causes failures when the repository is currently on a different branch (e.g., a feature branch from a previous task execution).

**Symptoms:**
- `git pull` fails when the repository is on a non-main branch
- Worker task fails completely instead of recovering
- Subsequent tasks cannot proceed even though the issue is recoverable

**Expected behavior:**
1. Check current branch before pulling
2. Switch to main branch before pulling
3. If any git operation fails, remove the repository directory and clone fresh
4. Handle errors gracefully without failing the entire task

**Actual behavior:**
- Directly runs `git pull` regardless of current branch
- Fails and raises exception when pull fails
- Does not attempt recovery by re-cloning

## Problem Statement
The `setup_repository` function (lines 400-470 in `worker/main.py`) lacks robust error handling and branch management. It assumes the repository is always on the main branch when attempting to pull updates, which is often not the case after previous ADW workflow executions that create feature branches. When the pull fails, the function raises an exception instead of recovering by removing and re-cloning the repository.

## Solution Statement
Modify the `setup_repository` function to:
1. When a repository exists, first switch to the main branch using `git checkout main`
2. Then pull the latest changes with `git pull`
3. If any git operation fails (checkout or pull), catch the exception, remove the repository directory completely, and clone it fresh as if it didn't exist
4. Ensure all error paths lead to a working repository state rather than task failure

This approach ensures resilience against stale repository states and provides automatic recovery from git-related errors.

## Steps to Reproduce
1. Execute an ADW task that creates a feature branch in the repository
2. Execute another ADW task on the same repository
3. The `setup_repository` function will attempt to pull while still on the feature branch
4. Git pull will fail, causing the entire task to fail
5. The repository remains in a broken state for subsequent tasks

## Root Cause Analysis
The root cause is insufficient git state management in the repository update logic. The function at lines 422-441 assumes:
- The repository is always on the main branch
- Git operations will always succeed
- No recovery mechanism is needed

The function currently:
```python
if repo_dir.exists():
    # Repository already exists, pull latest
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise Exception(f"Git pull failed: {result.stderr}")
```

This simplistic approach doesn't account for:
- Branch state from previous executions
- Uncommitted changes
- Merge conflicts
- Detached HEAD states
- Permission issues
- Network failures during pull

## Relevant Files
Use these files to fix the bug:

- **`worker/main.py`** (lines 400-470) - Contains the `setup_repository` function that needs to be fixed
  - This is the primary file where the bug exists
  - The function needs enhanced git operations and error recovery logic
  - Must handle branch switching before pulling
  - Must implement fallback to remove and re-clone on any error

## Step by Step Tasks

### Update setup_repository Function Logic
- Modify the repository update logic (lines 422-441) to check and switch to main branch before pulling
- Add `git checkout main` command before the `git pull` command
- Wrap git operations in a try-except block to catch any failures
- Implement error recovery: if checkout or pull fails, remove the repository directory using `shutil.rmtree(repo_dir)` and proceed to clone logic
- Ensure the function always returns a valid repository path in a clean state
- Update logging to reflect branch switching and error recovery actions
- Add status updates to inform users about branch switching and recovery operations

### Test Error Recovery Path
- Verify that when git operations fail, the directory is removed completely
- Verify that after removal, the function successfully clones the repository fresh
- Verify that the final repository state is on the main branch with latest changes
- Ensure no partial or corrupted repository states remain after errors

## Notes
- The fix should be surgical - only modify the `setup_repository` function
- Use `shutil.rmtree()` which is already imported in the file for directory removal
- The main branch name is assumed to be "main" - this is the GitHub standard and matches the repository structure
- The recovery mechanism (remove and re-clone) is preferred over attempting complex git recovery operations because:
  - It's simpler and more reliable
  - It guarantees a clean state
  - The overhead of re-cloning is acceptable for task resilience
  - It handles all possible git error scenarios (merge conflicts, detached HEAD, corrupted refs, etc.)
- Ensure all status messages sent to users are clear about what's happening (switching branches, recovering from errors)
- The `subprocess.run()` calls should maintain the same timeout values for consistency
- Consider that the repository URL with authentication token is only available in the clone path (line 453), so if re-cloning after error, we need to reconstruct it
