"""Context priming for ADW.

Generates priming commands based on detected project type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProjectType(Enum):
    """Detected project types."""

    PYTHON = "python"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    REACT = "react"
    VUE = "vue"
    NEXTJS = "nextjs"
    FASTAPI = "fastapi"
    DJANGO = "django"
    FLASK = "flask"
    UNKNOWN = "unknown"


@dataclass
class ProjectDetection:
    """Result of project type detection."""

    project_type: ProjectType
    framework: str | None = None
    test_framework: str | None = None
    config_files: list[str] | None = None


def detect_project_type(project_path: Path | None = None) -> ProjectDetection:
    """Detect the project type based on config files and structure.

    Args:
        project_path: Path to the project root. Uses cwd if not provided.

    Returns:
        ProjectDetection with detected type and framework info.
    """
    path = project_path or Path.cwd()

    # Check for Python
    pyproject = path / "pyproject.toml"
    requirements = path / "requirements.txt"
    setup_py = path / "setup.py"

    if pyproject.exists() or requirements.exists() or setup_py.exists():
        framework = None
        test_framework = "pytest"

        # Check pyproject.toml for framework
        if pyproject.exists():
            content = pyproject.read_text().lower()
            if "fastapi" in content:
                framework = "FastAPI"
            elif "django" in content:
                framework = "Django"
            elif "flask" in content:
                framework = "Flask"

        # Check requirements.txt
        if requirements.exists() and not framework:
            content = requirements.read_text().lower()
            if "fastapi" in content:
                framework = "FastAPI"
            elif "django" in content:
                framework = "Django"
            elif "flask" in content:
                framework = "Flask"

        if framework == "FastAPI":
            return ProjectDetection(
                project_type=ProjectType.FASTAPI,
                framework="FastAPI",
                test_framework=test_framework,
                config_files=["pyproject.toml"],
            )
        elif framework == "Django":
            return ProjectDetection(
                project_type=ProjectType.DJANGO,
                framework="Django",
                test_framework=test_framework,
                config_files=["pyproject.toml", "manage.py"],
            )
        elif framework == "Flask":
            return ProjectDetection(
                project_type=ProjectType.FLASK,
                framework="Flask",
                test_framework=test_framework,
                config_files=["pyproject.toml"],
            )
        else:
            return ProjectDetection(
                project_type=ProjectType.PYTHON,
                test_framework=test_framework,
                config_files=["pyproject.toml", "requirements.txt"],
            )

    # Check for Node.js/JavaScript/TypeScript
    package_json = path / "package.json"
    if package_json.exists():
        try:
            import json

            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Detect test framework
            detected_test_fw: str | None = None
            if "jest" in deps:
                detected_test_fw = "jest"
            elif "vitest" in deps:
                detected_test_fw = "vitest"
            elif "mocha" in deps:
                detected_test_fw = "mocha"

            # Detect framework
            if "next" in deps:
                return ProjectDetection(
                    project_type=ProjectType.NEXTJS,
                    framework="Next.js",
                    test_framework=detected_test_fw,
                    config_files=["package.json", "next.config.js"],
                )
            elif "vue" in deps:
                return ProjectDetection(
                    project_type=ProjectType.VUE,
                    framework="Vue.js",
                    test_framework=detected_test_fw,
                    config_files=["package.json", "vite.config.ts"],
                )
            elif "react" in deps:
                return ProjectDetection(
                    project_type=ProjectType.REACT,
                    framework="React",
                    test_framework=detected_test_fw,
                    config_files=["package.json"],
                )

            # Check for TypeScript
            if "typescript" in deps or (path / "tsconfig.json").exists():
                return ProjectDetection(
                    project_type=ProjectType.TYPESCRIPT,
                    test_framework=detected_test_fw,
                    config_files=["package.json", "tsconfig.json"],
                )

            return ProjectDetection(
                project_type=ProjectType.NODEJS,
                test_framework=detected_test_fw,
                config_files=["package.json"],
            )
        except (json.JSONDecodeError, KeyError):
            return ProjectDetection(
                project_type=ProjectType.NODEJS,
                config_files=["package.json"],
            )

    # Check for Go
    go_mod = path / "go.mod"
    if go_mod.exists():
        return ProjectDetection(
            project_type=ProjectType.GO,
            test_framework="go test",
            config_files=["go.mod"],
        )

    # Check for Rust
    cargo_toml = path / "Cargo.toml"
    if cargo_toml.exists():
        return ProjectDetection(
            project_type=ProjectType.RUST,
            test_framework="cargo test",
            config_files=["Cargo.toml"],
        )

    return ProjectDetection(project_type=ProjectType.UNKNOWN)


# Templates for generating prime commands
PRIME_TEMPLATES = {
    ProjectType.PYTHON: {
        "test_command": "pytest tests/ -v",
        "lint_command": "ruff check .",
        "format_command": "ruff format .",
        "type_check": "mypy src/",
        "patterns": [
            "Use type hints for all public functions",
            "Follow Google-style docstrings",
            "Test files in tests/ directory, prefixed with test_",
            "Use pytest fixtures for shared test setup",
        ],
    },
    ProjectType.FASTAPI: {
        "test_command": "pytest tests/ -v",
        "lint_command": "ruff check .",
        "format_command": "ruff format .",
        "type_check": "mypy src/",
        "patterns": [
            "Use Pydantic models for request/response validation",
            "Dependency injection for shared resources",
            "Router organization by feature/resource",
            "Use async/await for I/O operations",
        ],
    },
    ProjectType.DJANGO: {
        "test_command": "python manage.py test",
        "lint_command": "ruff check .",
        "format_command": "ruff format .",
        "patterns": [
            "Follow Django app structure",
            "Use class-based views where appropriate",
            "Models in models.py, views in views.py",
            "Use Django ORM for database operations",
        ],
    },
    ProjectType.FLASK: {
        "test_command": "pytest tests/ -v",
        "lint_command": "ruff check .",
        "format_command": "ruff format .",
        "patterns": [
            "Use Flask blueprints for organization",
            "Application factory pattern",
            "Use Flask-SQLAlchemy for database",
        ],
    },
    ProjectType.NODEJS: {
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "format_command": "npm run format",
        "patterns": [
            "Use ES modules (import/export)",
            "Handle errors with try/catch",
            "Use async/await for promises",
        ],
    },
    ProjectType.TYPESCRIPT: {
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "format_command": "npm run format",
        "type_check": "tsc --noEmit",
        "patterns": [
            "Use strict TypeScript configuration",
            "Define interfaces for data shapes",
            "Avoid 'any' type where possible",
            "Use type guards for narrowing",
        ],
    },
    ProjectType.REACT: {
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "format_command": "npm run format",
        "patterns": [
            "Use functional components with hooks",
            "Separate concerns: components, hooks, utils",
            "Use React.memo for expensive renders",
            "Prop types or TypeScript for type safety",
        ],
    },
    ProjectType.VUE: {
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "format_command": "npm run format",
        "patterns": [
            "Use Composition API for complex logic",
            "Single-file components (.vue)",
            "Pinia for state management",
            "Vue Router for navigation",
        ],
    },
    ProjectType.NEXTJS: {
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "format_command": "npm run format",
        "patterns": [
            "App Router for routing (app/ directory)",
            "Server Components by default",
            "Use 'use client' for client components",
            "API routes in app/api/",
        ],
    },
    ProjectType.GO: {
        "test_command": "go test ./...",
        "lint_command": "golangci-lint run",
        "format_command": "go fmt ./...",
        "patterns": [
            "Follow Go idioms and conventions",
            "Use interfaces for abstraction",
            "Error handling with explicit returns",
            "Tests in same package with _test.go suffix",
        ],
    },
    ProjectType.RUST: {
        "test_command": "cargo test",
        "lint_command": "cargo clippy",
        "format_command": "cargo fmt",
        "patterns": [
            "Use Result/Option for error handling",
            "Follow Rust naming conventions",
            "Document public APIs with /// comments",
            "Tests in same file or tests/ directory",
        ],
    },
}


def generate_prime_command(
    detection: ProjectDetection,
    command_type: str = "prime",
) -> str:
    """Generate a priming command based on project detection.

    Args:
        detection: The detected project information.
        command_type: Type of command (prime, prime_test, prime_bug, prime_docs).

    Returns:
        Markdown content for the priming command.
    """
    template = PRIME_TEMPLATES.get(detection.project_type, {})

    if command_type == "prime":
        return _generate_base_prime(detection, template)
    elif command_type == "prime_test":
        return _generate_test_prime(detection, template)
    elif command_type == "prime_bug":
        return _generate_bug_prime(detection, template)
    elif command_type == "prime_docs":
        return _generate_docs_prime(detection, template)
    else:
        return _generate_base_prime(detection, template)


def _generate_base_prime(detection: ProjectDetection, template: dict[str, Any]) -> str:
    """Generate base prime command content."""
    patterns = template.get("patterns", [])
    patterns_str = "\n".join(f"- {p}" for p in patterns)

    test_cmd = template.get("test_command", "echo 'No test command detected'")
    lint_cmd = template.get("lint_command", "echo 'No lint command detected'")

    framework_info = ""
    if detection.framework:
        framework_info = f"\n**Framework:** {detection.framework}"

    return f"""# Project Prime Context

Auto-generated priming context for this project.

**Type:** {detection.project_type.value}{framework_info}
**Test Framework:** {detection.test_framework or "unknown"}

## Key Patterns

{patterns_str}

## Commands

- **Test:** `{test_cmd}`
- **Lint:** `{lint_cmd}`
"""


def _generate_test_prime(detection: ProjectDetection, template: dict[str, Any]) -> str:
    """Generate test-specific prime content."""
    test_cmd = template.get("test_command", "echo 'No test command detected'")

    if detection.project_type in (
        ProjectType.PYTHON,
        ProjectType.FASTAPI,
        ProjectType.FLASK,
    ):
        test_structure = """
## Test Structure (Python/pytest)

```python
# Test file: tests/test_feature.py
import pytest
from mymodule import feature

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_feature_basic(sample_data):
    result = feature(sample_data)
    assert result is not None

def test_feature_edge_case():
    with pytest.raises(ValueError):
        feature(None)
```

## Mocking

```python
from unittest.mock import patch, MagicMock

@patch("mymodule.external_service")
def test_with_mock(mock_service):
    mock_service.return_value = "mocked"
    result = feature()
    assert result == "mocked"
```
"""
    elif detection.project_type == ProjectType.GO:
        test_structure = """
## Test Structure (Go)

```go
// feature_test.go
package feature

import "testing"

func TestFeature(t *testing.T) {
    result := Feature()
    if result != expected {
        t.Errorf("got %v, want %v", result, expected)
    }
}

func TestFeatureTableDriven(t *testing.T) {
    tests := []struct {
        name     string
        input    string
        expected string
    }{
        {"basic", "input", "output"},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := Feature(tt.input)
            if got != tt.expected {
                t.Errorf("got %v, want %v", got, tt.expected)
            }
        })
    }
}
```
"""
    elif detection.project_type == ProjectType.RUST:
        test_structure = """
## Test Structure (Rust)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_feature() {
        let result = feature();
        assert_eq!(result, expected);
    }

    #[test]
    #[should_panic(expected = "error message")]
    fn test_panics() {
        feature_that_panics();
    }
}
```
"""
    else:
        test_structure = """
## Test Structure (JavaScript/TypeScript)

```typescript
// feature.test.ts or feature.spec.ts
import { describe, it, expect, vi } from 'vitest'; // or jest
import { feature } from './feature';

describe('feature', () => {
  it('should work correctly', () => {
    const result = feature();
    expect(result).toBe(expected);
  });

  it('should handle edge cases', () => {
    expect(() => feature(null)).toThrow();
  });
});

// Mocking
vi.mock('./dependency', () => ({
  externalService: vi.fn().mockReturnValue('mocked'),
}));
```
"""

    return f"""# Test Context

Auto-generated testing context for this project.

**Test Command:** `{test_cmd}`
**Test Framework:** {detection.test_framework or "unknown"}
{test_structure}
"""


def _generate_bug_prime(detection: ProjectDetection, template: dict[str, Any]) -> str:
    """Generate bug-fixing prime content."""
    if detection.project_type in (
        ProjectType.PYTHON,
        ProjectType.FASTAPI,
        ProjectType.FLASK,
        ProjectType.DJANGO,
    ):
        error_patterns = """
## Error Handling (Python)

```python
# Standard pattern
try:
    result = operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise
except Exception as e:
    logger.exception("Unexpected error")
    raise RuntimeError("Operation failed") from e

# FastAPI error responses
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Not found")
```

## Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed info for debugging")
logger.info("Normal operation info")
logger.warning("Something unexpected but handled")
logger.error("Error occurred")
logger.exception("Error with stack trace")
```
"""
    elif detection.project_type == ProjectType.GO:
        error_patterns = """
## Error Handling (Go)

```go
// Standard pattern
result, err := operation()
if err != nil {
    return fmt.Errorf("operation failed: %w", err)
}

// Custom errors
type NotFoundError struct {
    ID string
}

func (e *NotFoundError) Error() string {
    return fmt.Sprintf("not found: %s", e.ID)
}

// Error checking
if errors.Is(err, ErrNotFound) {
    // handle not found
}
```

## Logging

```go
import "log"

log.Printf("Info: %v", value)
log.Fatalf("Fatal error: %v", err)
```
"""
    elif detection.project_type == ProjectType.RUST:
        error_patterns = """
## Error Handling (Rust)

```rust
// Using Result
fn operation() -> Result<Value, Error> {
    let result = try_operation()?;
    Ok(result)
}

// Custom errors with thiserror
#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("not found: {0}")]
    NotFound(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}
```

## Logging

```rust
use tracing::{debug, info, warn, error};

debug!("detailed info");
info!("normal operation");
warn!("unexpected but handled");
error!("error occurred: {}", err);
```
"""
    else:
        error_patterns = """
## Error Handling (JavaScript/TypeScript)

```typescript
// Standard pattern
try {
  const result = await operation();
} catch (error) {
  console.error('Operation failed:', error);
  throw new Error('Operation failed', { cause: error });
}

// Custom errors
class NotFoundError extends Error {
  constructor(id: string) {
    super(`Not found: ${id}`);
    this.name = 'NotFoundError';
  }
}
```

## Logging

```typescript
console.debug('Detailed info');
console.info('Normal operation');
console.warn('Warning');
console.error('Error:', error);
```
"""

    return f"""# Bug Investigation Context

Auto-generated debugging context for this project.

**Project Type:** {detection.project_type.value}
{error_patterns}
## Debug Commands

Find recent bug fixes:
```bash
git log --oneline --grep="fix\\|bug" -10
```

Find TODOs and FIXMEs:
```bash
git grep -n "TODO\\|FIXME\\|XXX\\|BUG"
```
"""


def _generate_docs_prime(detection: ProjectDetection, template: dict[str, Any]) -> str:
    """Generate documentation prime content."""
    if detection.project_type in (
        ProjectType.PYTHON,
        ProjectType.FASTAPI,
        ProjectType.FLASK,
        ProjectType.DJANGO,
    ):
        doc_patterns = """
## Docstring Style (Google)

```python
def function(param1: str, param2: int) -> bool:
    \"\"\"Brief description of the function.

    Longer description if needed. Explains what the function does
    in more detail.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.

    Example:
        >>> result = function("value", 42)
        >>> print(result)
        True
    \"\"\"
    pass
```

## Module Documentation

```python
\"\"\"Module description.

This module provides functionality for X.

Usage:
    from module import function
    result = function()
\"\"\"
```
"""
    elif detection.project_type == ProjectType.GO:
        doc_patterns = """
## Documentation Style (Go)

```go
// Package description.
//
// This package provides functionality for X.
package mypackage

// Function does something useful.
// It takes a string and returns an int.
func Function(input string) int {
    // ...
}

// Type represents a thing.
type Thing struct {
    // Field is used for something.
    Field string
}
```
"""
    elif detection.project_type == ProjectType.RUST:
        doc_patterns = """
## Documentation Style (Rust)

```rust
//! Crate-level documentation.
//!
//! This crate provides functionality for X.

/// Function description.
///
/// # Arguments
///
/// * `param` - Description of parameter
///
/// # Returns
///
/// Description of return value
///
/// # Examples
///
/// ```
/// let result = function("value");
/// assert_eq!(result, expected);
/// ```
pub fn function(param: &str) -> i32 {
    // ...
}
```
"""
    else:
        doc_patterns = """
## Documentation Style (JSDoc)

```typescript
/**
 * Brief description of the function.
 *
 * @param param1 - Description of param1
 * @param param2 - Description of param2
 * @returns Description of return value
 * @throws {Error} When something goes wrong
 *
 * @example
 * ```ts
 * const result = function("value", 42);
 * console.log(result);
 * ```
 */
function example(param1: string, param2: number): boolean {
  // ...
}
```
"""

    return f"""# Documentation Context

Auto-generated documentation context for this project.

**Project Type:** {detection.project_type.value}
{doc_patterns}
## Markdown Best Practices

- Use ATX-style headers (# Header)
- Include code examples in fenced blocks
- Use relative links for internal references
- Keep lines under 100 characters when possible
"""


def generate_all_prime_commands(
    project_path: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """Generate all priming commands for a project.

    Args:
        project_path: Path to project root.
        output_dir: Directory to write commands to (default: .claude/commands/).

    Returns:
        List of paths to generated command files.
    """
    path = project_path or Path.cwd()
    detection = detect_project_type(path)

    if detection.project_type == ProjectType.UNKNOWN:
        logger.warning("Could not detect project type")
        return []

    output = output_dir or (path / ".claude" / "commands")
    output.mkdir(parents=True, exist_ok=True)

    generated = []
    command_types = ["prime", "prime_test", "prime_bug", "prime_docs"]

    for cmd_type in command_types:
        content = generate_prime_command(detection, cmd_type)

        # Use _auto suffix to indicate auto-generated
        filename = f"{cmd_type}_auto.md"
        filepath = output / filename

        filepath.write_text(content)
        generated.append(filepath)
        logger.info(f"Generated {filepath}")

    return generated
