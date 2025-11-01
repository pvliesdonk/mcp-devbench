# Semantic Release Setup Instructions

This project now uses [Python Semantic Release](https://python-semantic-release.readthedocs.io/) for automated versioning and releases based on conventional commits.

## What's Been Set Up

The following has been configured:

1. **Semantic Release Configuration** in `pyproject.toml`:
   - Version management using semantic versioning
   - Conventional commit parsing (Angular style)
   - Automatic CHANGELOG.md updates
   - GitHub releases with artifacts

2. **GitHub Actions Workflow** (`.github/workflows/release.yml`):
   - Triggers on pushes to `main` branch
   - Runs tests before releasing
   - Automatically creates versions and tags based on commits
   - Publishes to PyPI (when configured)
   - Creates GitHub releases with release notes

3. **Dependencies**:
   - Added `python-semantic-release>=9.0.0` to dev dependencies

## Manual Steps Required

### 1. Configure PyPI API Token (Optional but Recommended)

To enable automatic publishing to PyPI:

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/token/)
2. Create a new API token with scope limited to your project
3. Go to your GitHub repository → Settings → Secrets and variables → Actions
4. Create a new secret named `PYPI_API_TOKEN` with your PyPI token

**Note:** If you don't want to publish to PyPI automatically, you can remove or comment out the PyPI publishing step in the workflow.

### 2. Use Conventional Commits

From now on, all commit messages should follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- **feat:** A new feature (triggers minor version bump, e.g., 0.1.0 → 0.2.0)
  ```
  feat: add support for custom Docker networks
  ```

- **fix:** A bug fix (triggers patch version bump, e.g., 0.1.0 → 0.1.1)
  ```
  fix: correct container cleanup race condition
  ```

- **BREAKING CHANGE:** Breaking changes (triggers major version bump, e.g., 0.1.0 → 1.0.0)
  ```
  feat!: redesign authentication API
  
  BREAKING CHANGE: The auth API has been completely redesigned
  ```

- **Other types** (don't trigger releases):
  - `docs:` Documentation changes
  - `style:` Code style changes
  - `refactor:` Code refactoring
  - `test:` Test updates
  - `chore:` Maintenance tasks
  - `ci:` CI/CD changes

### 3. First Release

To trigger your first semantic release:

1. Ensure all tests pass locally:
   ```bash
   uv run pytest
   ```

2. Commit any pending changes using conventional commits:
   ```bash
   git add .
   git commit -m "feat: initial semantic release setup"
   ```

3. Push to main branch:
   ```bash
   git push origin main
   ```

4. The workflow will automatically:
   - Run tests
   - Determine the new version based on commits since last release
   - Update version in `pyproject.toml`
   - Update `CHANGELOG.md`
   - Create a git tag (e.g., `v0.2.0`)
   - Create a GitHub release
   - Publish to PyPI (if configured)

### 4. Verify Setup

After the first successful run:

1. Check the Actions tab in GitHub to see the workflow run
2. Check the Releases page for the new release
3. Verify CHANGELOG.md has been updated
4. Verify the version in pyproject.toml has been updated
5. (Optional) Check PyPI for the published package

## How It Works

### Automatic Versioning

Python Semantic Release analyzes your commit history since the last release and determines the next version:

- Commits with `feat:` → minor version bump (0.1.0 → 0.2.0)
- Commits with `fix:` → patch version bump (0.1.0 → 0.1.1)
- Commits with `BREAKING CHANGE:` → major version bump (0.1.0 → 1.0.0)
- Other commits → no release

### When Releases Happen

- **Automatically:** On every push to `main` that contains release-worthy commits
- **Manually:** You can trigger a release using the "Actions" tab → "Semantic Release" → "Run workflow"

### What Gets Published

Each release includes:
1. Updated `pyproject.toml` with new version
2. Updated `CHANGELOG.md` with all changes
3. Git tag (e.g., `v0.2.0`)
4. GitHub Release with auto-generated release notes
5. PyPI package (if configured)

## Troubleshooting

### No Release Created

If no release is created after pushing to main:
- Check if your commits follow conventional commit format
- Ensure commits contain `feat:` or `fix:` (other types don't trigger releases)
- Check the Actions logs for errors

### Version Not Updated

- Semantic Release will only create a release if there are new commits with release types
- If you force push or rewrite history, it might affect version detection

### PyPI Publishing Failed

- Verify your `PYPI_API_TOKEN` secret is set correctly
- Ensure the token has appropriate permissions for your package
- Check if the package name is available on PyPI (for first release)

## Additional Resources

- [Python Semantic Release Documentation](https://python-semantic-release.readthedocs.io/)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
