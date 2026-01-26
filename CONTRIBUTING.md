# Contributing Guidelines

## Git Workflow

### Branching Strategy

We use **feature branches**:

- `main` - production-ready code
- `feature/{story-name}` - for new features/stories
- `fix/{description}` - for bug fixes

### Branch Naming

```
feature/satellite-collector
feature/weather-collector
fix/auth-token-refresh
```

### Creating a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/{story-name}
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
