"""Pydantic config models with validation."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class VisionConfig(BaseModel):
    """Vision model API configuration."""

    provider: str = "nim"
    nim_function_id: str = "24e0c62b-f7d0-44ba-8012-012c2a1aaf31"
    nim_max_tokens: int = Field(default=1024, ge=64, le=4096)
    fallback_provider: str = "groq"
    groq_model: str = "llama-3.2-11b-vision"
    groq_max_tokens: int = Field(default=1024, ge=64, le=4096)

    @property
    def nim_api_key(self) -> str:
        key = os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            from vision_browser.exceptions import ConfigError
            raise ConfigError(
                "NVIDIA_API_KEY not set. Export it: export NVIDIA_API_KEY='nvapi-...'"
            )
        return key

    @property
    def groq_api_key(self) -> str:
        return os.environ.get("GROQ_API_KEY", "")


class BrowserConfig(BaseModel):
    """Browser automation configuration."""

    tool: str = "agent-browser"
    annotate: bool = True
    viewport: tuple[int, int] = (1280, 720)
    timeout_ms: int = Field(default=30000, ge=5000, le=120000)
    session_name: str = ""  # Empty = no persistence
    cdp_url: str = ""  # Empty = launch local Chrome; set to Brave CDP

    @field_validator("viewport")
    @classmethod
    def validate_viewport(cls, v: tuple[int, int]) -> tuple[int, int]:
        w, h = v
        if w < 320 or h < 240:
            raise ValueError("Viewport must be at least 320x240")
        if w > 7680 or h > 4320:
            raise ValueError("Viewport exceeds 8K resolution")
        return v


class DesktopConfig(BaseModel):
    """Desktop control fallback configuration."""

    screenshot_cmd: str = "scrot"
    type_delay_ms: int = Field(default=20, ge=0, le=500)


class OrchestratorConfig(BaseModel):
    """Orchestrator loop configuration."""

    max_turns: int = Field(default=20, ge=1, le=100)
    batch_actions: bool = True
    diff_mode: bool = False  # Alias for auto_diff_screenshots
    auto_diff_screenshots: bool = False  # Enable differential screenshot capture
    diff_threshold: float = Field(default=0.01, ge=0.0, le=1.0)  # Pixel diff ratio threshold
    diff_max_retain: int = Field(default=10, ge=1, le=100)  # Max diffs to keep per session
    max_prompt_elements: int = Field(default=30, ge=5, le=100)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_base: float = Field(default=1.0, ge=0.1, le=10.0)
    rate_limit_delay: float = Field(default=0.5, ge=0.0, le=60.0)

    # Circuit breaker for Vision API resilience
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout: float = Field(default=60.0, ge=5.0, le=600.0)
    circuit_breaker_successes: int = Field(default=2, ge=1, le=10)


class AppConfig(BaseModel):
    """Root application configuration."""

    vision: VisionConfig = Field(default_factory=VisionConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> AppConfig:
        """Load config from YAML file, falling back to defaults."""
        import yaml

        config_paths: list[Path] = []
        if path:
            config_paths.append(Path(path))
        config_paths.extend([
            Path("config.yaml"),
            Path(__file__).parent.parent.parent / "config.yaml",
            Path.home() / ".config" / "vision-browser" / "config.yaml",
        ])

        data: dict = {}
        for p in config_paths:
            if p.exists():
                with open(p) as f:
                    data = yaml.safe_load(f) or {}
                break

        return cls.model_validate(data)
