# Release Process

MCP DevBench uses semantic versioning and automated releases.

## Versioning

Format: `MAJOR.MINOR.PATCH`

- **MAJOR:** Breaking changes
- **MINOR:** New features
- **PATCH:** Bug fixes

## Release Workflow

Releases are automated via semantic-release:

1. Merge PR to main
2. CI runs tests
3. Semantic-release analyzes commits
4. Version bumped
5. CHANGELOG.md updated
6. Git tag created
7. Package published
8. GitHub release created

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add container snapshots
fix: resolve race condition
docs: update API documentation
```

Types:
- `feat:` - New feature (MINOR bump)
- `fix:` - Bug fix (PATCH bump)
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Tests
- `chore:` - Maintenance

## Breaking Changes

```
feat!: change API response format

BREAKING CHANGE: Response format changed from X to Y
```

This triggers a MAJOR version bump.

## Manual Release

If needed:

```bash
# Bump version
python-semantic-release version

# Publish
python-semantic-release publish
```
