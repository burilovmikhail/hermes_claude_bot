# Bug: GitHub CLI Authentication Failure Due to Environment Variable Mismatch

## Bug Description
The GitHub CLI operations fail with "The github cli is not authenticated" error even when the `GITHUB_TOKEN` environment variable is set. This occurs in Docker containers where the system is configured to use `GITHUB_TOKEN`, but the Python code in `adws/adw_modules/` is looking for `GITHUB_PAT` instead. This mismatch causes all GitHub CLI operations (creating PRs, posting comments, fetching issues) to fail with authentication errors.

**Symptoms:**
- Error message: "The github cli is not authenticated"
- `GITHUB_TOKEN` is properly set in the environment (confirmed in .env.example and worker/entrypoint.sh)
- GitHub CLI commands fail to authenticate despite token being available

**Expected Behavior:**
- GitHub CLI operations should successfully authenticate using the `GITHUB_TOKEN` environment variable
- All `gh` commands should work with the provided token

**Actual Behavior:**
- GitHub CLI operations fail because the code looks for `GITHUB_PAT` instead of `GITHUB_TOKEN`
- The `get_github_env()` function returns `None` when `GITHUB_PAT` is not found, even though `GITHUB_TOKEN` is available

## Problem Statement
There is an inconsistency in environment variable naming between the Docker/system configuration and the Python application code. The Docker setup, .env.example, and entrypoint.sh all reference `GITHUB_TOKEN`, which is the standard GitHub environment variable name. However, the Python code in `adws/adw_modules/github.py` and `adws/adw_modules/agent.py` attempts to read `GITHUB_PAT` instead, causing a mismatch that prevents GitHub CLI authentication from working.

## Solution Statement
Update the Python code in `adws/adw_modules/github.py` and `adws/adw_modules/agent.py` to check for `GITHUB_TOKEN` (the standard GitHub environment variable) as the primary source, with a fallback to `GITHUB_PAT` for backward compatibility. The code should also set both `GH_TOKEN` and `GITHUB_TOKEN` in the subprocess environment to ensure GitHub CLI can authenticate properly.

## Steps to Reproduce
1. Set `GITHUB_TOKEN` environment variable in Docker container or local environment
2. Run any ADW workflow that requires GitHub CLI operations (e.g., creating a PR, posting comments)
3. Observe that GitHub CLI operations fail with "not authenticated" error
4. Check the code in `adws/adw_modules/github.py:40` - it looks for `GITHUB_PAT` which doesn't exist
5. The `get_github_env()` function returns `None`, causing subprocess calls to fail authentication

## Root Cause Analysis
The root cause is in two files:

1. **adws/adw_modules/github.py:40** - The `get_github_env()` function reads from `GITHUB_PAT`:
   ```python
   github_pat = os.getenv("GITHUB_PAT")
   ```

2. **adws/adw_modules/agent.py:126** - The `get_claude_env()` function also reads from `GITHUB_PAT`:
   ```python
   github_pat = os.getenv("GITHUB_PAT")
   ```

However, the actual environment variable being set is `GITHUB_TOKEN`:
- `.env.example:33` specifies `GITHUB_TOKEN=ghp_your-github-token`
- `worker/entrypoint.sh:30-32` checks for `GITHUB_TOKEN`
- GitHub CLI automatically recognizes `GITHUB_TOKEN` as documented in GitHub's official documentation

The mismatch occurs because:
1. The code tries to read `GITHUB_PAT`
2. It doesn't find it (because `GITHUB_TOKEN` is set instead)
3. Returns `None`, causing GitHub CLI to have no authentication token
4. All GitHub operations fail with "not authenticated" error

## Relevant Files
Use these files to fix the bug:

- **adws/adw_modules/github.py** - Contains `get_github_env()` function that needs to check for `GITHUB_TOKEN` instead of `GITHUB_PAT`. This file handles all GitHub CLI operations including issue fetching, comment posting, and repository operations.

- **adws/adw_modules/agent.py** - Contains `get_claude_env()` function that also needs to check for `GITHUB_TOKEN` instead of `GITHUB_PAT`. This file sets up the environment for Claude Code agent execution and needs to pass the correct token to subprocess calls.

### New Files
No new files need to be created for this bug fix.

## Step by Step Tasks

### Update github.py to use GITHUB_TOKEN
- Modify `get_github_env()` function in `adws/adw_modules/github.py:40` to check for `GITHUB_TOKEN` first, with fallback to `GITHUB_PAT` for backward compatibility
- Update the docstring to reflect that both `GITHUB_TOKEN` (primary) and `GITHUB_PAT` (fallback) are supported
- Ensure both `GH_TOKEN` and `GITHUB_TOKEN` are set in the returned environment dictionary to cover all GitHub CLI authentication methods
- Update comments to clarify the environment variable priority: `GITHUB_TOKEN` (standard) → `GITHUB_PAT` (legacy)

### Update agent.py to use GITHUB_TOKEN
- Modify `get_claude_env()` function in `adws/adw_modules/agent.py:126` to check for `GITHUB_TOKEN` first, with fallback to `GITHUB_PAT` for backward compatibility
- Update the docstring comments to reflect the new environment variable priority
- Ensure both `GH_TOKEN` and `GITHUB_TOKEN` are set in the returned environment dictionary
- Update inline comments to clarify that `GITHUB_TOKEN` is the standard variable name and `GITHUB_PAT` is kept for backward compatibility

### Verify consistency across codebase
- Verify that no other files reference `GITHUB_PAT` in a way that would break with this change
- Confirm that .env.example correctly documents `GITHUB_TOKEN` as the variable to use
- Ensure worker/entrypoint.sh continues to work with `GITHUB_TOKEN`

## Notes
- **Backward Compatibility**: The fix includes a fallback to `GITHUB_PAT` to ensure existing deployments that use `GITHUB_PAT` continue to work without requiring immediate changes.

- **Standard Naming**: `GITHUB_TOKEN` is the standard environment variable name used by GitHub Actions, GitHub CLI, and most GitHub integrations. Using this name improves compatibility and reduces confusion.

- **Why both GH_TOKEN and GITHUB_TOKEN**: GitHub CLI recognizes both `GH_TOKEN` and `GITHUB_TOKEN`, but setting both ensures maximum compatibility. `GH_TOKEN` is the official GitHub CLI variable, while `GITHUB_TOKEN` is the standard used by GitHub Actions and other tools.

- **No .env changes required**: Since .env.example already uses `GITHUB_TOKEN`, users following the documentation will already have the correct variable set. This fix aligns the code with the existing documentation.

- **Testing recommendation**: After applying the fix, test with:
  1. Only `GITHUB_TOKEN` set (standard case)
  2. Only `GITHUB_PAT` set (backward compatibility)
  3. Both set (should prefer `GITHUB_TOKEN`)
