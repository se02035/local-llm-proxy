# Local LLM Proxy

This tool provides an **optional** developer setup for using self-hosted OSS models (e.g., `qwen2.5-coder:14b`) through a LiteLLM proxy, allowing seamless integration with Cursor.

Using this setup helps reduce API costs, improves resiliency, and keeps the model configuration easily swappable behind a standardized OpenAI-compatible endpoint.

## Prerequisites

1.  **Docker & Docker Compose**: Required to run the LiteLLM proxy, database, and Ngrok containers.
2.  **Ollama (Native)**: Required to run the local model. Install the Ollama app natively on your machine (e.g., from ollama.com) to ensure full GPU/Apple Silicon acceleration.
3.  **Ngrok Account**: Required to tunnel the local proxy to the internet securely. You need your `NGROK_AUTHTOKEN`.
4.  **`curl`**: Required for `test-setup.sh` (the script checks for `curl` before sending HTTP requests to Ollama and LiteLLM).
5.  **`jq`**: Required for the `test-setup.sh` validation script to parse JSON responses. (`brew install jq`)

## Quick Start

### 1. Configure the Environment

Copy the example environment file and customize it if necessary:

```bash
cp src/config/.env.example src/config/.env
```

By default, the `.env` file exposes LiteLLM on port `4000` and configures a secure dummy key (`sk-local-agent-secure-12345`) for Cursor to use.

### 2. Start the Proxy and Services

Start the proxy containers and fetch the public Ngrok URL automatically by using the provided wrapper script:

```bash
./src/proxy.sh start
```

**Stop the Proxy:**
When you are done, you can tear down the setup with:
```bash
./src/proxy.sh stop
```

**Manual Start:**
If you prefer not to use the wrapper script, you can start the containers and fetch the URL manually:
```bash
docker compose -f src/config/docker-compose.yml --env-file src/config/.env up -d
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
```

**Accessing Admin UIs:**
- **LiteLLM UI:** Accessible at `http://localhost:4000/ui` (or via the Ngrok URL) using the `UI_USERNAME` and `UI_PASSWORD` configured in your `.env`.
  - *Note:* The `LITELLM_MASTER_KEY` is an admin key used for authentication. It will **not** appear in the "Keys" list in the Admin UI. To see a key in that list (e.g., for usage tracking), you can manually create a "Virtual Key" in the UI.

### 3. Load the Recommended Model

Run the model loader script to automatically pull the recommended quantized model natively via Ollama:

```bash
./src/load-model.sh
```

*(Note: For machines with limited RAM, 14B parameter models with 4-bit quantization are recommended to balance performance and RAM usage.)*

### 4. Validate the Setup

Run the end-to-end validation script to ensure the proxy is correctly communicating with your local Ollama model:

```bash
./test/test-setup.sh
```

If everything is configured correctly, the script will output a success message and the generated response.

### 5. Configure Cursor

Once validated, open Cursor settings and add the local proxy:

1.  **Models**: Click **+ Add Custom Model** and add the specific model name configured in LiteLLM (e.g., `gpt-4o`). Enable the toggle next to it.
2.  **Override OpenAI Base URL**: Enter your Ngrok public URL with `/cursor` appended (e.g., `https://<your-ngrok-url>/cursor`). **Do not use `/v1`**.
3.  **API Key**: Enter the value of `LITELLM_MASTER_KEY` from your `.env` file.

Now, when you use `gpt-4o` in Cursor, it will route securely through LiteLLM to your local Ollama instance.

> **Note:** Supported modes are Ask and Plan. Agent mode doesn't support custom API keys yet.
