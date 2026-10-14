# Releasing

1. Update `pyproject.toml` and `src/sessionlens/__init__.py` versions together.
2. Run unit tests and a clean wheel installation smoke test.
3. Review tracked files: synthetic fixtures only, no real sessions or reports.
4. Push the repository and wait for the OS/Python CI matrix to pass.
5. Push an annotated `vX.Y.Z` tag. The workflow tests again, builds a wheel and source distribution, and creates a GitHub Release with artifacts.

The repository installs directly with `uv tool install git+https://github.com/wangjinjie722/sessionlens.git`. For a pinned version, append `@v0.1.0`. A GitHub Release wheel can also be installed with pipx or pip. No PyPI publication is configured.

Do not publish personal reports. `reports/`, `.env`, virtual environments, and `dist/` are ignored. GitHub release artifacts must come from the reviewed source tree.
