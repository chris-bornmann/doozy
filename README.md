
Install UV for package management -
curl -LsSf https://astral.sh/uv/install.sh | sudo sh

Create the project.
mkdir ~/dev/doozy/server
cd ~/dev/doozy/server
uv init --name doozy

This creates an empty README.md, a main.py, a pyproject.toml, a .gitignore, and a .git repo.

WHAT DO ALL THESE DO DIFFERENTLY?
      --bare
          Only create a `pyproject.toml`
      --package
          Set up the project to be built as a Python package
      --no-package
          Do not set up the project to be built as a Python package
      --app
          Create a project for an application
      --lib
          Create a project for a library
      --script
          Create a script
      --build-backend <BUILD_BACKEND>
          Initialize a build-backend of choice for the project [env:
          UV_INIT_BUILD_BACKEND=] [possible values: uv, hatch, flit, pdm, poetry,
          setuptools, maturin, scikit]
      --author-from <AUTHOR_FROM>
          Fill in the `authors` field in the `pyproject.toml` [possible values:
          auto, git, none]
      --no-pin-python
          Do not create a `.python-version` file for the project
      --no-workspace
          Avoid discovering a workspace and create a standalone project


# Add SqlModel -
```
uv add sqlmodel
```
This also adds SqlAlchemy, Pydantic, etc.

# Add FastAPI -
```
uv add "fastapi[standard]"
uv add fastapi-pagination
```

# Add Ruff, and Ty, but only to dev environments.
```
uv add --dev ruff
uv add --dev ty
uv run ruff check
uv run ty check
```

# Run It
```
uv run fastapi dev src/app/main.py
export PYTHONPATH=/Users/cbb/dev/doozy/server/src
```
