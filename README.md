# Local LLM Proxy

This repository provides a **Python CLI** for a small developer setup: run **Ollama** on your machine, expose it through a **LiteLLM** OpenAI-compatible proxy with **PostgreSQL**, and optionally tunnel it with **ngrok** so tools like Cursor can use a public base URL.

The goal is a single, repeatable workflow (no shell scripts): configure files under `config/`, then use `local-llm-proxy` for lifecycle, models, and validation.

## Repository layout

| Path | Purpose |
|------|---------|
| `src/local_llm_proxy/` | Click CLI and service logic |
| `config/` | Docker Compose, LiteLLM YAML, and environment templates |
| `config/.env` | Your local secrets (copy from `.env.example`; gitignored) |
| `tests/` | Pytest unit tests |

## Prerequisites

1. **Python 3.10+** (3.11 recommended; matches CI).
2. **Docker** and **Docker Compose** (for LiteLLM and Postgres containers; ngrok is optional).
3. **Ollama** installed and running on the host (native install for best GPU support).
4. **Ngrok account** and `NGROK_AUTHTOKEN` (optional — only required for public tunneling).

## Install the CLI (development)

From the repository root:

```bash
python -m pip install -e ".[dev]"
```

This installs the `local-llm-proxy` command and development dependencies (`pytest`, `ruff`, `pre-commit`).

## Configuration

1. Copy the example environment file:

   ```bash
   cp .env.example config/.env
   ```

2. Edit `config/.env` with your values (admin key for the proxy, database credentials, and Ollama settings. `NGROK_AUTHTOKEN` is only needed when using `--public`). See comments in `.env.example`.

3. **LiteLLM routing** is defined in a YAML file passed to `setup start` with optional `--litellm-config` (if omitted, default `config/litellm-config.yaml` is used). Align the Ollama-related variables in `.env` with how your containers reach the host Ollama service (see comments in `.env.example`).

## Using the CLI

**Start (local only, default)** the stack (Compose project rooted at `config/`):

```bash
local-llm-proxy setup start
```

This starts LiteLLM on localhost only (no ngrok tunnel).

**Start with public tunnel (optional):**

```bash
local-llm-proxy setup start --public
```

Optionally point to a different LiteLLM config file:

```bash
local-llm-proxy setup start --litellm-config path/to/litellm-config.yaml
local-llm-proxy setup start --public --litellm-config path/to/litellm-config.yaml
```

**Stop**:

```bash
local-llm-proxy setup stop
```

**Restart**:

```bash
local-llm-proxy setup restart
local-llm-proxy setup restart --public
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


**Cursor setup tip (optional):**
If you tunnel with ngrok and use Cursor, set **Override OpenAI Base URL** to your ngrok URL with `/cursor` appended.
Use the **Virtual key** printed by `local-llm-proxy setup start --public` (line starts with `Virtual key:`) as Cursor's API key; do not use your personal OpenAI key.

## Code quality and tests

**Lint (Ruff):**

```bash
ruff check .
```

**Unit tests:**

```bash
pytest -q
```

**Pre-commit** (runs Ruff and yamllint via hooks defined in `.pre-commit-config.yaml`):

```bash
pre-commit install
pre-commit run --all-files
```

CI runs three parallel jobs on relevant pull requests: `pre-commit` (Ruff + yamllint), `pytest`, and a non-running `docker compose config` validation (see `.github/workflows/python-cli-quality.yml`).

## License

See `LICENSE` in the repository root.
