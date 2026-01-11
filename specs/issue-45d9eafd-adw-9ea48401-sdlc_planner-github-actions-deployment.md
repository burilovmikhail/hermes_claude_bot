# Feature: GitHub Actions Automated Deployment Workflow

## Feature Description
Implement a GitHub Actions workflow that automatically deploys the Hermes Telegram Bot application to a remote host when pull requests are merged to the main branch. The workflow will SSH into the production server, pull the latest code changes, and rebuild/restart the Docker containers using docker-compose. This enables continuous deployment (CD) to streamline the release process and ensure the production environment stays up-to-date with minimal manual intervention.

## User Story
As a **project maintainer**
I want to **automatically deploy code to production when PRs merge to main**
So that **new features and fixes are deployed quickly without manual SSH and deployment commands**

## Problem Statement
Currently, deploying the Hermes bot requires manual intervention: SSHing into the production host, running git pull, and executing docker-compose up -d --build. This manual process is:
- Time-consuming and repetitive
- Error-prone (forgetting steps, wrong commands)
- Blocks rapid iteration and deployment
- Requires the maintainer to have immediate access to perform deployments

## Solution Statement
Create a GitHub Actions workflow that triggers on PR merge to main branch. The workflow will:
1. Use GitHub Secrets to securely store SSH credentials (host IP, SSH private key)
2. Establish SSH connection to the production server
3. Navigate to the application directory
4. Pull the latest code from the main branch
5. Rebuild and restart Docker containers using docker-compose up -d --build
6. Provide deployment status feedback in the GitHub Actions UI

## Relevant Files
Use these files to implement the feature:

- **docker-compose.yml** (line 1-86) - Defines the multi-container application structure (bot, worker, mongodb, redis) that needs to be rebuilt and restarted during deployment
- **Dockerfile** (line 1-36) - Bot service container build instructions that docker-compose will use during deployment
- **worker/Dockerfile** - Worker service container build instructions referenced by docker-compose
- **README.md** (line 45-88) - Documents deployment procedures that this workflow will automate

### New Files
- **.github/workflows/deploy.yml** - The GitHub Actions workflow definition that will handle automated deployment on PR merge to main

## Implementation Plan

### Phase 1: Foundation
Set up the GitHub Actions workflow infrastructure and directory structure. Create the .github/workflows directory if it doesn't exist, and establish the basic workflow file with proper triggers for PR merges to main branch.

### Phase 2: Core Implementation
Implement the SSH-based deployment logic within the workflow. Configure secure credential management using GitHub Secrets, establish SSH connection using actions/checkout and ssh-agent, and execute the deployment commands (git pull and docker-compose up -d --build) on the remote host.

### Phase 3: Integration
Add error handling, status reporting, and documentation. Ensure the workflow provides clear feedback on deployment success or failure, document the required GitHub Secrets configuration, and update the README with information about the automated deployment process.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### Create GitHub Actions Directory Structure
- Create the `.github` directory in the project root if it doesn't exist
- Create the `.github/workflows` subdirectory to house workflow files
- Verify directory structure is correct for GitHub Actions to recognize workflows

### Implement Deployment Workflow File
- Create `.github/workflows/deploy.yml` with proper YAML structure
- Configure workflow to trigger on `pull_request` events with type `closed` and branch `main`, filtered to only run when PR is merged
- Set appropriate workflow name and permissions

### Configure SSH Connection Setup
- Add step to install SSH client dependencies if needed
- Configure SSH agent using `webfactory/ssh-agent@v0.9.0` action (industry standard for SSH key management)
- Load SSH private key from GitHub Secret `SSH_PRIVATE_KEY`
- Add step to add remote host to known_hosts to prevent SSH verification prompts
- Use GitHub Secret `HOST_IP` for the target server address

### Implement Git Pull Command via SSH
- Execute SSH command to connect to the remote host using `HOST_IP` secret
- Navigate to the correct application directory (should be configurable via secret or hardcoded to typical path)
- Run `git pull origin main` to fetch latest code changes
- Add error handling to catch git pull failures

### Implement Docker Compose Rebuild Command via SSH
- Execute SSH command to run `docker compose up -d --build` on remote host
- Ensure command runs in the correct directory where docker-compose.yml is located
- Use `--build` flag to force rebuild of images with new code
- Use `-d` flag for detached mode to prevent workflow hanging

### Add Workflow Status Reporting
- Add step to report deployment success/failure status
- Include basic logging of deployment steps for debugging
- Consider adding notification step for deployment failures (optional)

### Update Documentation
- Add section to README.md explaining the automated deployment workflow
- Document required GitHub Secrets that need to be configured:
  - `SSH_PRIVATE_KEY`: Private SSH key with access to production server
  - `HOST_IP`: IP address or hostname of production server
- Document the deployment process and how to monitor workflow runs
- Add troubleshooting section for common deployment issues

### Test Workflow Configuration
- Create a test branch to validate workflow syntax
- Verify workflow file is properly formatted YAML
- Check that secrets are referenced correctly
- Consider dry-run testing or staging environment validation

## Testing Strategy

### Unit Tests
This feature primarily involves infrastructure-as-code and doesn't require traditional unit tests. However, validation should include:
- **YAML Validation**: Ensure the workflow YAML is syntactically correct and follows GitHub Actions schema
- **Secret Reference Testing**: Verify all GitHub Secrets are properly referenced and available
- **SSH Connection Testing**: Test SSH connection to production host with the configured credentials
- **Command Execution Testing**: Validate that git pull and docker-compose commands execute successfully

### Edge Cases
- **PR closed without merge**: Workflow should not trigger if PR is closed without merging
- **Failed git pull**: Workflow should fail gracefully if git pull encounters errors (conflicts, network issues)
- **Docker build failure**: Workflow should report clear error if docker-compose build fails
- **SSH connection timeout**: Handle scenarios where SSH connection cannot be established
- **Invalid SSH key**: Detect and report when SSH_PRIVATE_KEY secret is invalid or malformed
- **Host unreachable**: Handle cases where HOST_IP is unreachable or incorrect
- **Concurrent deployments**: Ensure workflow handles multiple simultaneous PR merges appropriately
- **Missing secrets**: Workflow should fail with clear message if required secrets are not configured
- **Wrong directory on remote host**: Handle cases where the application directory doesn't exist or has moved
- **Insufficient permissions**: Handle scenarios where SSH user lacks permissions to run git/docker commands

## Acceptance Criteria
- [ ] GitHub Actions workflow file exists at `.github/workflows/deploy.yml`
- [ ] Workflow triggers automatically when a PR is merged to main branch
- [ ] Workflow does NOT trigger when a PR is closed without merging
- [ ] Workflow successfully establishes SSH connection using `HOST_IP` and `SSH_PRIVATE_KEY` secrets
- [ ] Workflow executes `git pull` command on remote host and updates code to latest main branch
- [ ] Workflow executes `docker compose up -d --build` to rebuild and restart all containers
- [ ] Workflow provides clear success/failure status in GitHub Actions UI
- [ ] README.md includes documentation on required GitHub Secrets setup
- [ ] README.md includes information about automated deployment process
- [ ] All sensitive credentials (SSH key, host IP) are stored in GitHub Secrets, not hardcoded
- [ ] Workflow includes basic error handling for common failure scenarios
- [ ] Manual testing confirms successful deployment from PR merge to production

## Notes
- **GitHub Secrets Setup**: Repository maintainer must manually configure secrets in GitHub repository settings (Settings → Secrets and variables → Actions)
  - `SSH_PRIVATE_KEY`: The full private SSH key content (begins with `-----BEGIN OPENSSH PRIVATE KEY-----`)
  - `HOST_IP`: The IP address or hostname of the production server (e.g., `192.168.1.100` or `example.com`)

- **SSH Key Format**: Ensure SSH private key is in OpenSSH format. If using PEM format, may need to convert using `ssh-keygen -p -m PEM -f keyfile`

- **Remote Host Path**: The workflow assumes a specific directory path on the remote host. Consider adding a `DEPLOY_PATH` secret if the application is not in a standard location (e.g., `/home/user/hermes_claude_bot`)

- **SSH User**: The workflow assumes the SSH key authenticates as a specific user. This user must have:
  - Read/write access to the application directory
  - Permission to run docker and docker-compose commands (typically requires sudo or docker group membership)
  - Git configured with appropriate credentials if the repository is private

- **Security Considerations**:
  - Use a dedicated deployment SSH key, not a personal key
  - Restrict SSH key permissions on the remote host to only necessary operations
  - Consider using GitHub Environments with protection rules for additional deployment gates
  - Regularly rotate SSH keys and secrets

- **Docker Compose Version**: Ensure the remote host has docker-compose v2 (Docker Compose CLI plugin) or adjust command to `docker-compose` (legacy) if needed

- **Potential Enhancements** (future iterations):
  - Add Slack/Telegram notification on deployment success/failure
  - Implement deployment rollback mechanism on failure
  - Add health check step after deployment to verify services are running
  - Use GitHub Environments to support staging vs production deployments
  - Add manual approval gate before production deployment
  - Implement blue-green deployment or zero-downtime deployment strategy

- **Alternative Tools Considered**:
  - Could use dedicated CD tools like Ansible, Jenkins, or GitLab CI instead of GitHub Actions
  - Could use Docker registry and pull images instead of building on remote host
  - Could use container orchestration platforms (Kubernetes, Docker Swarm) for more sophisticated deployments
  - GitHub Actions was chosen for simplicity, tight integration with GitHub, and zero additional infrastructure requirements
