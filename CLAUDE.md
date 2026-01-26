# Claude Instructions

**You must read and follow CONTRIBUTING.md before making any changes.**

## Critical Rules

1. **ALWAYS fetch/pull before any work** - Sync with remote first
2. **NEVER commit to main branch** - Always use feature branches
3. **Check current branch first** - Run `git branch` before any work
4. **All code needs tests** - No exceptions for new features or collectors
5. **Commit before switching branches** - Don't lose work

## Workflow

Before starting any task:

```bash
# 1. ALWAYS sync with remote first
git fetch origin
git status

# 2. Check which branch you're on
git branch

# 3. If on main and need to make changes, create a feature branch
git pull origin main
git checkout -b feature/{task-name}

# 4. If on existing feature branch, pull latest
git pull origin main --rebase

# 5. Verify you're on the correct branch
git branch
```

## When Writing Code

1. Write the implementation
2. Write tests for the implementation
3. Ensure tests pass before committing
4. Use `--dry-run` and `--limit` flags for manual testing

## Test Requirements

- Unit tests for all new functions/classes
- Mock external APIs (use `responses` library)
- Add `pytest.ini` to new services
- Mark integration tests with `@pytest.mark.integration`

## CLI Flags for Collectors

All collectors must support:
- `--dry-run` - Run without side effects
- `--limit N` - Limit results for testing
- `--verbose` - Enable debug logging
