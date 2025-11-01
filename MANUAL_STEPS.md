# Manual Steps for Semantic Release Setup

This document outlines all manual steps you need to take to complete the semantic release setup.

## ✅ What's Already Done

The following has been automatically configured:

1. **Python Semantic Release**: Added as a dev dependency (`python-semantic-release>=9.0.0`)
2. **Semantic Release Configuration**: Complete configuration in `pyproject.toml` with:
   - Conventional commit parsing
   - Automatic version bumping based on commit types
   - CHANGELOG.md auto-generation
   - GitHub release creation
3. **GitHub Actions Workflow**: New `.github/workflows/release.yml` that:
   - Triggers on every push to `main` branch
   - Can also be manually triggered via workflow_dispatch
   - Runs tests before releasing
   - Automatically determines version from commits
   - Creates tags and GitHub releases
   - Publishes to PyPI (when token is configured)

## 🔧 Manual Steps Required

### Step 1: Configure PyPI API Token (Required for PyPI Publishing)

**If you want to publish to PyPI automatically:**

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Give it a name (e.g., "mcp-devbench-github-actions")
4. Set scope to "Entire account" or create after first manual upload with "Project: mcp-devbench"
5. Copy the generated token (starts with `pypi-`)
6. Go to your GitHub repository: https://github.com/pvliesdonk/mcp-devbench/settings/secrets/actions
7. Click "New repository secret"
8. Name: `PYPI_API_TOKEN`
9. Value: Paste the PyPI token
10. Click "Add secret"

**If you don't want to publish to PyPI:**
- Remove or comment out the "Publish package to PyPI" step in `.github/workflows/release.yml`

### Step 2: Enable GitHub Actions

Ensure GitHub Actions has write permissions:

1. Go to https://github.com/pvliesdonk/mcp-devbench/settings/actions
2. Under "Workflow permissions", select "Read and write permissions"
3. Check "Allow GitHub Actions to create and approve pull requests"
4. Click "Save"

### Step 3: Start Using Conventional Commits

From now on, **all commits** to the `main` branch should follow the Conventional Commits format:

#### Commit Format
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Commit Types and Version Impact

| Type | Description | Version Bump | Example |
|------|-------------|--------------|---------|
| `feat:` | New feature | **Minor** (0.1.0 → 0.2.0) | `feat: add container networking support` |
| `fix:` | Bug fix | **Patch** (0.1.0 → 0.1.1) | `fix: correct memory leak in exec manager` |
| `perf:` | Performance improvement | **Patch** (0.1.0 → 0.1.1) | `perf: optimize database queries` |
| `BREAKING CHANGE:` | Breaking change | **Major** (0.1.0 → 1.0.0) | See example below |
| `docs:` | Documentation only | No release | `docs: update API reference` |
| `style:` | Code style changes | No release | `style: format with ruff` |
| `refactor:` | Code refactoring | No release | `refactor: simplify container manager` |
| `test:` | Test updates | No release | `test: add unit tests for auth` |
| `chore:` | Maintenance tasks | No release | `chore: update dependencies` |
| `ci:` | CI/CD changes | No release | `ci: update workflow` |

#### Breaking Change Example
```
feat!: redesign authentication API

BREAKING CHANGE: The authentication API has been completely redesigned.
The old token-based auth is no longer supported. Users must migrate to
the new OAuth2 flow.
```

### Step 4: Test the Workflow

**Option A: Merge this PR and let it run automatically**
1. Merge this PR to `main`
2. The workflow will automatically run
3. Since this PR contains `feat:` commits, it should create version 0.2.0

**Option B: Test with a manual trigger first**
1. Merge this PR to `main`
2. Go to https://github.com/pvliesdonk/mcp-devbench/actions/workflows/release.yml
3. Click "Run workflow"
4. Select branch: `main`
5. Click "Run workflow"
6. Monitor the workflow run in the Actions tab

### Step 5: Verify First Release

After the workflow runs successfully, verify:

1. **Version updated**: Check `pyproject.toml` - version should be bumped
2. **CHANGELOG updated**: Check `CHANGELOG.md` - new version entry added
3. **Git tag created**: Check https://github.com/pvliesdonk/mcp-devbench/tags
4. **GitHub release**: Check https://github.com/pvliesdonk/mcp-devbench/releases
5. **PyPI package** (if configured): Check https://pypi.org/project/mcp-devbench/

## 📝 Usage Examples

### Typical Development Workflow

```bash
# Make your changes
git add .

# Commit with conventional format
git commit -m "feat: add support for custom networks"

# Push to main (after PR approval)
git push origin main

# Semantic release will automatically:
# 1. Detect this is a "feat" commit → minor version bump
# 2. Update version in pyproject.toml (e.g., 0.1.0 → 0.2.0)
# 3. Update CHANGELOG.md
# 4. Create git tag v0.2.0
# 5. Create GitHub release
# 6. Publish to PyPI
```

### Multiple Changes in One Release

```bash
# Multiple commits are analyzed together
git commit -m "feat: add new feature A"
git commit -m "feat: add new feature B"
git commit -m "fix: correct bug in feature A"
git push origin main

# Result: One release with version bump based on highest priority change
# In this case: minor bump (0.1.0 → 0.2.0) due to "feat" commits
# CHANGELOG will include all changes
```

### Creating a Breaking Change Release

```bash
git commit -m "feat!: redesign API

BREAKING CHANGE: API endpoints have been redesigned.
Old endpoints are no longer available."

git push origin main

# Result: Major version bump (0.1.0 → 1.0.0)
```

## 🔍 Troubleshooting

### Problem: No release created after pushing to main

**Possible causes:**
- Commits don't include `feat:`, `fix:`, or breaking changes
- All commits are `docs:`, `chore:`, `test:`, etc. (which don't trigger releases)
- Commits don't follow conventional commit format

**Solution:** Check commit messages and ensure at least one uses `feat:` or `fix:`

### Problem: Workflow failed at PyPI publishing step

**Possible causes:**
- `PYPI_API_TOKEN` secret not configured
- Token expired or invalid
- Package name already taken (first release)

**Solution:** 
1. Verify token is correctly set in GitHub secrets
2. For first release, you may need to manually upload once: `uv build && uv run twine upload dist/*`
3. Then regenerate token scoped to the project

### Problem: Version not updated in pyproject.toml

**Check:**
1. Was the workflow run on the `main` branch?
2. Did the workflow complete successfully?
3. Check workflow logs in Actions tab

### Problem: CHANGELOG not updated

**Check:**
1. Ensure `CHANGELOG.md` exists (it should from previous setup)
2. Check workflow logs for errors
3. Verify semantic-release configuration in `pyproject.toml`

## 📚 Additional Resources

- **Python Semantic Release Docs**: https://python-semantic-release.readthedocs.io/
- **Conventional Commits**: https://www.conventionalcommits.org/
- **Semantic Versioning**: https://semver.org/
- **GitHub Actions Workflow Syntax**: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions

## 🆘 Getting Help

If you encounter issues:
1. Check the Actions tab logs: https://github.com/pvliesdonk/mcp-devbench/actions
2. Verify all secrets are configured correctly
3. Review the SEMANTIC_RELEASE_SETUP.md file for more details
4. Check if the issue is related to commit format or configuration

## Next Steps

1. ✅ Configure PyPI API token (Step 1)
2. ✅ Enable GitHub Actions write permissions (Step 2)
3. ✅ Start using conventional commits (Step 3)
4. ✅ Test the workflow (Step 4)
5. ✅ Verify first release (Step 5)

Good luck! 🚀
