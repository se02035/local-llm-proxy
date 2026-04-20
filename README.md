# Local LLM Proxy

This repository provides a **Python CLI** for a small developer setup: run **Ollama** on your machine, expose it through a **LiteLLM** OpenAI-compatible proxy with **PostgreSQL**, and optionally tunnel it with **ngrok** so tools like Cursor can use a public base URL.

The goal is a single, repeatable workflow (no shell scripts): configure files under `config/`, then use `local-llm-proxy` for lifecycle, models, and validation.

## Repository layout

| Path | Purpose |
|------|---------|
| `src/local_llm_proxy/` | Click CLI and service logic |
| `config/` | Docker Compose, LiteLLM YAML, and environment templates |
| `config/.env` | Your local secrets (copy from `config/.env.example`; gitignored) |
| `tests/` | Pytest unit tests |

## Prerequisites

1. **Python 3.10+** (3.11 recommended; matches CI).
2. **Docker** and **Docker Compose** (for LiteLLM, Postgres, ngrok containers).
3. **Ollama** installed and running on the host (native install for best GPU support).
4. **Ngrok account** and `NGROK_AUTHTOKEN` for public tunneling.

## Install the CLI (development)

From the repository root:

```bash
python -m pip install -e ".[dev]"
```

This installs the `local-llm-proxy` command and development dependencies (`pytest`, `ruff`, `pre-commit`).

## Configuration

1. Copy the example environment file:

   ```bash
   cp config/.env.example config/.env
   ```

2. Edit `config/.env` with your values (admin key for the proxy, database credentials, ngrok token, and the settings your compose file expects). See comments in `config/.env.example`.

3. **LiteLLM routing** is defined in a YAML file passed to `setup start` with `--litellm-config` (default: `config/litellm-config.yaml`). Align the Ollama-related variables in `.env` with how your containers reach the host Ollama service (see comments in `config/.env.example`).

## Using the CLI

**Start** the stack (Compose project rooted at `config/`):

```bash
local-llm-proxy setup start --litellm-config config/litellm-config.yaml
```

**Stop**:

```bash
local-llm-proxy setup stop
```

**Restart**:

```bash
local-llm-proxy setup restart
```

**Ollama models** (runs `ollama` on your host):

```bash
local-llm-proxy models add <model-name>
local-llm-proxy models remove <model-name>
local-llm-proxy models list
```

**Validate** that Ollama responds and LiteLLM accepts a chat completion (uses the admin key from `config/.env`):

```bash
local-llm-proxy validate
```

**Manual Compose** (equivalent to what the CLI runs):

```bash
docker compose -f config/docker-compose.yml --env-file config/.env up -d
```

## Code quality and tests

**Lint (Ruff):**

```bash
ruff check .
```

**Unit tests:**

```bash
pytest -q
```

**Pre-commit** (runs Ruff via hooks defined in `.pre-commit-config.yaml`):

```bash
pre-commit install
pre-commit run --all-files
```

CI runs Ruff, pytest, a non-running `docker compose config` check, and yamllint on `config/` when relevant paths change (see `.github/workflows/python-cli-quality.yml`).

## License

See `LICENSE` in the repository root.
