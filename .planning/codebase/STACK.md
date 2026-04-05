# STACK.md -- Technology Stack

## Languages

| Language | Version | Role |
|----------|---------|------|
| Python | 3.14 (`.python-version` pin) | Primary -- all application logic |
| JavaScript | ES2020+ | DOM badge injection (`inject.js`) |

## Runtime

- **CPython 3.14** (enforced via `.python-version`)
- **uv** -- package manager and virtual environment orchestrator (replaces pip/venv)
- **hatchling** -- build backend (specified in `pyproject.toml`)

## Frameworks & Libraries

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| `playwright` | >=1.40.0 | Browser automation via CDP (persistent connection) |
| `playwright-stealth` | (latest) | Anti-detection browser fingerprinting |
| `groq` | >=0.13.0 | Groq API client (fallback vision model) |
| `httpx` | >=0.27.0 | HTTP client for NVIDIA NIM API calls |
| `pydantic` | >=2.0.0 | Config model validation (`AppConfig`, `VisionConfig`, etc.) |
| `rich` | >=13.0.0 | Console output -- panels, styled text, progress |
| `pillow` | >=10.0.0 | Image handling (future screenshot processing) |
| `pyyaml` | >=6.0 | YAML config file loading |

## Development Tools

| Tool | Purpose |
|------|---------|
| `uv` | Dependency management, virtual environment, script execution |
| `pytest` | >=8.0.0 -- unit testing framework |
| `ruff` | >=0.4.0 -- linting and formatting |

## Vision AI Providers

| Provider | Model | API Type | Role |
|----------|-------|----------|------|
| **NVIDIA NIM** | Llama 3.2 90B Vision | NVCF REST API (`https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{id}`) | Primary vision model |
| **Groq** | llama-3.2-11b-vision | Python SDK (`groq.Groq`) | Fallback vision model |

## External System Dependencies

| System | Tool | Purpose |
|--------|------|---------|
| Browser (CDP) | Brave/Chrome `--remote-debugging-port=9222` | Persistent browser connection |
| Browser (CLI) | `agent-browser` (npm global package) | Legacy browser automation |
| Desktop screenshot | `scrot` | Desktop screenshot capture (fallback mode) |
| Desktop input | `xdotool` | Mouse/keyboard simulation (fallback mode) |

## Authentication

| Credential | Environment Variable | Used By |
|------------|---------------------|---------|
| NVIDIA API Key | `NVIDIA_API_KEY` | `VisionConfig.nim_api_key` property |
| Groq API Key | `GROQ_API_KEY` | `VisionConfig.groq_api_key` property |

Both keys are **never** stored in config files -- loaded from environment only.
