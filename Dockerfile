# docker build -t doozy-app .  
# docker run -p 8000:8000 --mount type=bind,source=./database.db,target=/server/database.db doozy-app
# docker run -p 8000:8000 -it --mount type=bind,source=./database.db,target=/server/database.db doozy-app /bin/bash
#   uv run fastapi run src/app/main.py
# docker run -p 8000:8000 -v database.db:/server/database.db doozy-app

# Stage 1: Build environment
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

WORKDIR /server

# Copy pyproject.toml and uv.lock (if you have one)
COPY pyproject.toml .
COPY uv.lock .

# Install dependencies using uv sync --locked
RUN uv sync --locked --no-dev

# Stage 2: Runtime environment
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /server

# Copy the virtual environment from the builder stage
COPY --from=builder /server/.venv /server/.venv

# Copy your application code
COPY src /server/src

# Set the UV_PROJECT_ENVIRONMENT to the copied virtual environment
ENV UV_PROJECT_ENVIRONMENT="/server/.venv"
ENV PYTHONPATH="/server/src"

# Expose the port your FastAPI application will run on
EXPOSE 8000

# Command to run your FastAPI application with uvicorn
# CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["uv", "run", "fastapi", "run", "src/app/main.py", "--host", "0.0.0.0", "--port", "8000"]

