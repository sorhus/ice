# Contributing Guidelines

**IMPORTANT: Claude and all contributors must follow these guidelines.**

## Git Workflow

### Branching Strategy

We use **feature branches** - **NEVER commit directly to main**:

- `main` - production-ready code, protected
- `feature/{story-name}` - for new features/stories
- `fix/{description}` - for bug fixes

### Branch Rules

1. **Always pull before any work**: `git fetch origin && git status`
2. **Always work on a feature branch**, never on main
3. **Check your current branch** before making changes: `git branch`
4. **Create a new branch** if you're on main
5. **Commit changes to the feature branch** before switching branches
6. **Each story/feature gets its own branch**

### Before Starting Any Work

```bash
# ALWAYS run this first to sync with remote
git fetch origin
git status

# If behind origin/main, pull first
git pull origin main
```

### Branch Naming

```
feature/satellite-collector
feature/weather-collector
fix/auth-token-refresh
```

### Creating a Feature Branch

```bash
# Always start from main
git checkout main
git pull origin main
git checkout -b feature/{story-name}

# Verify you're on the correct branch
git branch
```

### Switching Between Branches

```bash
# Commit or stash changes before switching
git add .
git commit -m "WIP: description"

# Then switch
git checkout feature/other-branch
```

## Commits

Use **simple descriptive** commit messages:

- Start with a verb (Add, Fix, Update, Remove, Refactor)
- Keep the first line under 72 characters
- Add details in the body if needed

**Good examples:**
```
Add OAuth2 authentication for Copernicus API
Fix token refresh when expired during download
Update SMHI API client to handle rate limiting
Remove unused config options
```

**Avoid:**
```
WIP
fixes
Updated stuff
```

## Pull Requests

- **Features/stories**: Always create a PR
- **Small fixes**: Can commit directly to main (typos, minor adjustments)

### PR Process

1. Push your feature branch
2. Create PR against `main`
3. Add description of changes
4. Request review if applicable
5. Merge when approved

### PR Title Format

Same as commit messages - simple and descriptive:
```
Add satellite image collector with Sentinel-1 and Sentinel-2 support
```

## Code Style

- Python: Follow PEP 8
- Use type hints where practical
- Keep functions focused and small
- Add docstrings for public APIs

## Docker

- All code runs in Docker containers
- Test locally with `docker compose` before pushing
- Keep images minimal (use slim base images)

## Testing

### Requirements

**All new code must include tests.** This applies to:

- New collectors or services
- New features in existing code
- Bug fixes (add a test that would have caught the bug)

### Test Structure

Each collector/service should have a `tests/` directory:

```
collectors/
├── satellite/
│   ├── src/
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py
│       ├── test_client.py
│       └── test_main.py
```

### Test Types

1. **Unit Tests** (required)
   - Test individual functions and classes
   - No network calls - use mocks
   - Fast to run

2. **Integration Tests** (optional, marked with `@pytest.mark.integration`)
   - Test with real APIs
   - Require credentials in environment
   - Run with: `pytest -m integration`

### Running Tests

```bash
# Run all tests for a collector
docker compose run --rm satellite-collector pytest tests/

# Run with coverage
docker compose run --rm satellite-collector pytest tests/ --cov=src

# Run only unit tests (skip integration)
docker compose run --rm satellite-collector pytest tests/ -m "not integration"
```

### Test Dependencies

Add to `requirements.txt`:
```
pytest>=7.0.0
pytest-mock>=3.0.0
pytest-cov>=4.0.0
responses>=0.23.0
```

### Manual Testing

All collectors support manual runs with CLI flags:

```bash
# Dry-run mode (no side effects)
docker compose run --rm satellite-collector python src/download.py --dry-run

# Limit results for quick testing
docker compose run --rm satellite-collector python src/download.py --limit 1

# Verbose logging
docker compose run --rm satellite-collector python src/download.py --verbose
```
