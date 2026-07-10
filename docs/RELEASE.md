Release checklist
=================

This document describes the minimal steps to create a release and publish
to TestPyPI/PyPI.

1. Bump version
   - Update `version` in `pyproject.toml` (e.g. `0.1.0 -> 0.1.1`).
   - Update `CHANGELOG.md` with release notes.

2. Run tests and linters locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
black --check .
pytest -q
```

3. Build distributions

```powershell
python -m build
# artifacts are in dist/
```

4. Upload to TestPyPI (recommended first)

```powershell
$env:TWINE_USERNAME = '__token__'
$env:TWINE_PASSWORD = '<TEST_PYPI_TOKEN>'
python -m twine upload --repository testpypi dist/*
Remove-Item Env:TWINE_USERNAME; Remove-Item Env:TWINE_PASSWORD
```

5. Install from TestPyPI to validate

```powershell
pip install --index-url https://test.pypi.org/simple/ --no-deps netbox-topology-explorer==X.Y.Z
```

6. Publish to PyPI (optional)

If you use the repository GitHub Actions `publish` workflow, uploading to
PyPI is performed automatically when you push a `v*` tag. In that case you
do not need to run the `twine upload` command locally — use the CI instead.

If you prefer to publish manually instead of using CI, use the commands
below (requires a PyPI API token):

```powershell
$env:TWINE_USERNAME = '__token__'
$env:TWINE_PASSWORD = '<PYPI_TOKEN>'
python -m twine upload dist/*
Remove-Item Env:TWINE_USERNAME; Remove-Item Env:TWINE_PASSWORD
```

7. Tag & push

```powershell
git tag vX.Y.Z
git push origin --tags
```

8. Create GitHub release (optional)

- Create a release on GitHub matching the tag and paste the changelog notes.

CI / GitHub Actions
-------------------

This repository includes a `publish` workflow that will build and publish
the package when a tag matching `v*` is pushed, or when you trigger the
workflow manually.

- Repository secrets required:
   - `PYPI_API_TOKEN` — PyPI API token (for real publish)
   - `TEST_PYPI_TOKEN` — TestPyPI API token (optional, for manual test publishes)

- To publish automatically: bump the version, commit, tag and push the tag:

```powershell
git tag vX.Y.Z
git push origin --tags
```

- To publish manually (TestPyPI) from the Actions UI: Actions → Publish Python Package → Run workflow → set `repository=testpypi` and run.

- Verify run: open the workflow run in GitHub Actions and inspect the `publish` job logs. If the job fails, the logs include the `twine` output and HTTP response from PyPI/TestPyPI.

Notes
-----
- The workflow performs linting, tests and builds before publishing. Ensure the tag points to the commit that has the bumped `version` and updated `CHANGELOG.md`.
- Keep tokens in GitHub secrets only. Do not hardcode them in files or the repository.

Secrets
-------
- Store `PYPI_API_TOKEN` and `TEST_PYPI_TOKEN` in GitHub repository Secrets.

Notes
-----
- Always use API tokens (username `__token__`).
- Verify `MANIFEST.in` and `tool.setuptools.package-data` include templates/static files.
