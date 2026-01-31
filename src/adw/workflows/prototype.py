"""Prototype workflows for rapid application generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PrototypeConfig:
    """Configuration for a prototype type."""
    name: str
    plan_command: str
    description: str
    output_dir: str
    file_patterns: list[str]


# Available prototype types
PROTOTYPES: dict[str, PrototypeConfig] = {
    "vite_vue": PrototypeConfig(
        name="Vite + Vue",
        plan_command="/plan_vite_vue",
        description="Modern Vue 3 application with TypeScript and Vite",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "vite.config.ts",
            "tsconfig.json",
            "src/App.vue",
            "src/main.ts",
            "src/components/*.vue",
            "index.html",
        ],
    ),
    "uv_script": PrototypeConfig(
        name="UV Script",
        plan_command="/plan_uv_script",
        description="Single-file Python CLI with inline dependencies",
        output_dir="apps/{app_name}",
        file_patterns=[
            "main.py",  # With /// script header
        ],
    ),
    "bun_scripts": PrototypeConfig(
        name="Bun TypeScript",
        plan_command="/plan_bun_scripts",
        description="TypeScript application with Bun runtime",
        output_dir="apps/{app_name}",
        file_patterns=[
            "package.json",
            "tsconfig.json",
            "src/index.ts",
            "src/**/*.ts",
        ],
    ),
    "uv_mcp": PrototypeConfig(
        name="MCP Server",
        plan_command="/plan_uv_mcp",
        description="Model Context Protocol server for Claude",
        output_dir="apps/{app_name}",
        file_patterns=[
            "server.py",
            "pyproject.toml",
        ],
    ),
    "fastapi": PrototypeConfig(
        name="FastAPI",
        plan_command="/plan_fastapi",
        description="FastAPI backend with async support",
        output_dir="apps/{app_name}",
        file_patterns=[
            "pyproject.toml",
            "app/main.py",
            "app/routes/*.py",
            "app/models/*.py",
        ],
    ),
}


def get_prototype_config(prototype_type: str) -> PrototypeConfig | None:
    """Get configuration for a prototype type."""
    return PROTOTYPES.get(prototype_type)


def list_prototypes() -> list[PrototypeConfig]:
    """List all available prototype types."""
    return list(PROTOTYPES.values())
