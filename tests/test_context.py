"""Tests for context engineering module (Phase 3).

Tests priming detection, command generation, and context bundles.
"""

from __future__ import annotations

import gzip
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from adw.context import (
    Bundle,
    BundleFile,
    PRIME_TEMPLATES,
    ProjectType,
    delete_bundle,
    detect_project_type,
    diff_bundles,
    generate_all_prime_commands,
    generate_prime_command,
    get_bundle_file_contents,
    list_bundles,
    load_bundle,
    save_bundle,
    suggest_bundles,
)
from adw.context.bundles import compress_old_bundles
from adw.context.priming import ProjectDetection


# =============================================================================
# Project Detection Tests
# =============================================================================


class TestProjectDetection:
    """Tests for project type detection."""

    def test_detect_python_project(self, tmp_path: Path) -> None:
        """Detect Python project from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.PYTHON
        assert detection.test_framework == "pytest"

    def test_detect_fastapi_project(self, tmp_path: Path) -> None:
        """Detect FastAPI project from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n[project.dependencies]\nfastapi = "^0.100.0"\n'
        )

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.FASTAPI
        assert detection.framework == "FastAPI"

    def test_detect_django_project(self, tmp_path: Path) -> None:
        """Detect Django project from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("django==4.0.0\n")

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.DJANGO
        assert detection.framework == "Django"

    def test_detect_flask_project(self, tmp_path: Path) -> None:
        """Detect Flask project from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("flask==2.0.0\n")

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.FLASK
        assert detection.framework == "Flask"

    def test_detect_nodejs_project(self, tmp_path: Path) -> None:
        """Detect Node.js project from package.json."""
        (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {}}')

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.NODEJS

    def test_detect_typescript_project(self, tmp_path: Path) -> None:
        """Detect TypeScript project from package.json with typescript."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "devDependencies": {"typescript": "^5.0.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.TYPESCRIPT

    def test_detect_react_project(self, tmp_path: Path) -> None:
        """Detect React project from package.json."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "dependencies": {"react": "^18.0.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.REACT
        assert detection.framework == "React"

    def test_detect_vue_project(self, tmp_path: Path) -> None:
        """Detect Vue project from package.json."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "dependencies": {"vue": "^3.0.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.VUE
        assert detection.framework == "Vue.js"

    def test_detect_nextjs_project(self, tmp_path: Path) -> None:
        """Detect Next.js project from package.json."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "dependencies": {"next": "^13.0.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.NEXTJS
        assert detection.framework == "Next.js"

    def test_detect_go_project(self, tmp_path: Path) -> None:
        """Detect Go project from go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test\n\ngo 1.20\n")

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.GO
        assert detection.test_framework == "go test"

    def test_detect_rust_project(self, tmp_path: Path) -> None:
        """Detect Rust project from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')

        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.RUST
        assert detection.test_framework == "cargo test"

    def test_detect_unknown_project(self, tmp_path: Path) -> None:
        """Unknown project type when no config files found."""
        detection = detect_project_type(tmp_path)

        assert detection.project_type == ProjectType.UNKNOWN

    def test_detect_test_framework_jest(self, tmp_path: Path) -> None:
        """Detect Jest test framework."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "devDependencies": {"jest": "^29.0.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.test_framework == "jest"

    def test_detect_test_framework_vitest(self, tmp_path: Path) -> None:
        """Detect Vitest test framework."""
        (tmp_path / "package.json").write_text(
            '{"name": "test", "dependencies": {"vue": "^3.0.0"}, "devDependencies": {"vitest": "^0.30.0"}}'
        )

        detection = detect_project_type(tmp_path)

        assert detection.test_framework == "vitest"


# =============================================================================
# Prime Command Generation Tests
# =============================================================================


class TestPrimeCommandGeneration:
    """Tests for priming command generation."""

    def test_generate_base_prime(self) -> None:
        """Generate base prime command."""
        detection = ProjectDetection(
            project_type=ProjectType.PYTHON,
            test_framework="pytest",
        )

        content = generate_prime_command(detection, "prime")

        assert "Python" in content or "python" in content
        assert "pytest" in content

    def test_generate_test_prime_python(self) -> None:
        """Generate test prime for Python project."""
        detection = ProjectDetection(
            project_type=ProjectType.PYTHON,
            test_framework="pytest",
        )

        content = generate_prime_command(detection, "prime_test")

        assert "pytest" in content
        assert "@pytest.fixture" in content

    def test_generate_test_prime_go(self) -> None:
        """Generate test prime for Go project."""
        detection = ProjectDetection(
            project_type=ProjectType.GO,
            test_framework="go test",
        )

        content = generate_prime_command(detection, "prime_test")

        assert "go test" in content
        assert "testing" in content

    def test_generate_bug_prime(self) -> None:
        """Generate bug prime command."""
        detection = ProjectDetection(
            project_type=ProjectType.FASTAPI,
            framework="FastAPI",
        )

        content = generate_prime_command(detection, "prime_bug")

        assert "Error Handling" in content
        assert "HTTPException" in content

    def test_generate_docs_prime(self) -> None:
        """Generate docs prime command."""
        detection = ProjectDetection(
            project_type=ProjectType.PYTHON,
        )

        content = generate_prime_command(detection, "prime_docs")

        assert "Docstring" in content or "docstring" in content

    def test_generate_all_commands(self, tmp_path: Path) -> None:
        """Generate all prime commands for a project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        output_dir = tmp_path / ".claude" / "commands"

        generated = generate_all_prime_commands(tmp_path, output_dir)

        assert len(generated) == 4
        assert all(f.name.endswith("_auto.md") for f in generated)
        assert (output_dir / "prime_auto.md").exists()
        assert (output_dir / "prime_test_auto.md").exists()
        assert (output_dir / "prime_bug_auto.md").exists()
        assert (output_dir / "prime_docs_auto.md").exists()

    def test_prime_templates_exist_for_all_types(self) -> None:
        """Ensure templates exist for all non-unknown project types."""
        for ptype in ProjectType:
            if ptype != ProjectType.UNKNOWN:
                assert ptype in PRIME_TEMPLATES, f"Missing template for {ptype}"


# =============================================================================
# Bundle Tests
# =============================================================================


class TestBundleFile:
    """Tests for BundleFile dataclass."""

    def test_bundle_file_to_dict(self) -> None:
        """Convert BundleFile to dict."""
        bf = BundleFile(
            path="src/main.py",
            lines_start=1,
            lines_end=100,
            content_hash="abc12345",
            size_bytes=5000,
        )

        d = bf.to_dict()

        assert d["path"] == "src/main.py"
        assert d["lines_start"] == 1
        assert d["lines_end"] == 100
        assert d["content_hash"] == "abc12345"
        assert d["size_bytes"] == 5000

    def test_bundle_file_from_dict(self) -> None:
        """Create BundleFile from dict."""
        data = {
            "path": "src/utils.py",
            "lines_start": 10,
            "lines_end": 50,
            "content_hash": "def67890",
            "size_bytes": 2000,
        }

        bf = BundleFile.from_dict(data)

        assert bf.path == "src/utils.py"
        assert bf.lines_start == 10
        assert bf.lines_end == 50


class TestBundle:
    """Tests for Bundle dataclass."""

    def test_bundle_to_dict(self) -> None:
        """Convert Bundle to dict."""
        bundle = Bundle(
            task_id="test123",
            created_at=datetime(2026, 1, 31, 12, 0, 0),
            files=[
                BundleFile(path="src/main.py", lines_start=1, lines_end=100),
            ],
            description="Test bundle",
            total_lines=100,
            tags=["test", "example"],
        )

        d = bundle.to_dict()

        assert d["task_id"] == "test123"
        assert d["description"] == "Test bundle"
        assert len(d["files"]) == 1
        assert d["tags"] == ["test", "example"]

    def test_bundle_from_dict(self) -> None:
        """Create Bundle from dict."""
        data = {
            "task_id": "abc456",
            "created_at": "2026-01-31T14:30:00",
            "files": [
                {"path": "src/app.py", "lines_start": 1, "lines_end": 200}
            ],
            "description": "App bundle",
            "total_lines": 200,
            "tags": ["app"],
        }

        bundle = Bundle.from_dict(data)

        assert bundle.task_id == "abc456"
        assert bundle.file_count == 1
        assert bundle.total_lines == 200

    def test_bundle_file_paths(self) -> None:
        """Get set of file paths from bundle."""
        bundle = Bundle(
            task_id="test",
            created_at=datetime.now(),
            files=[
                BundleFile(path="src/a.py"),
                BundleFile(path="src/b.py"),
                BundleFile(path="src/a.py"),  # Duplicate
            ],
        )

        paths = bundle.file_paths

        assert paths == {"src/a.py", "src/b.py"}

    def test_bundle_summary(self) -> None:
        """Get human-readable bundle summary."""
        bundle = Bundle(
            task_id="test123",
            created_at=datetime(2026, 1, 31, 12, 0, 0),
            files=[BundleFile(path="src/main.py")],
            total_lines=100,
        )

        summary = bundle.summary()

        assert "test123" in summary
        assert "1 files" in summary
        assert "100 lines" in summary


# =============================================================================
# Bundle Save/Load Tests
# =============================================================================


class TestBundleSaveLoad:
    """Tests for saving and loading bundles."""

    def test_save_bundle(self, tmp_path: Path) -> None:
        """Save a bundle to disk."""
        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main():\n    pass\n")
        (src_dir / "utils.py").write_text("def helper():\n    return True\n")

        bundle = save_bundle(
            task_id="test123",
            files=["src/main.py", "src/utils.py"],
            description="Test bundle",
            tags=["test"],
            base_path=tmp_path,
        )

        assert bundle.task_id == "test123"
        assert bundle.file_count == 2
        assert bundle.description == "Test bundle"
        assert "test" in bundle.tags

        # Verify file was created
        bundle_path = tmp_path / ".adw" / "bundles" / "test123.json"
        assert bundle_path.exists()

    def test_save_bundle_with_dict_files(self, tmp_path: Path) -> None:
        """Save a bundle with dict file entries."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("line1\nline2\nline3\nline4\nline5\n")

        bundle = save_bundle(
            task_id="dict_test",
            files=[
                {"path": "src/main.py", "lines_start": 1, "lines_end": 3},
            ],
            base_path=tmp_path,
        )

        assert bundle.files[0].lines_start == 1
        assert bundle.files[0].lines_end == 3

    def test_save_bundle_skips_missing_files(self, tmp_path: Path) -> None:
        """Save bundle skips files that don't exist."""
        bundle = save_bundle(
            task_id="missing_test",
            files=["nonexistent.py", "also_missing.py"],
            base_path=tmp_path,
        )

        assert bundle.file_count == 0

    def test_save_bundle_skips_binary_files(self, tmp_path: Path) -> None:
        """Save bundle skips binary files."""
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "text.txt").write_text("hello")

        bundle = save_bundle(
            task_id="binary_test",
            files=["image.png", "text.txt"],
            base_path=tmp_path,
        )

        assert bundle.file_count == 1
        assert bundle.files[0].path == "text.txt"

    def test_load_bundle(self, tmp_path: Path) -> None:
        """Load a bundle from disk."""
        # First save a bundle
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("app code")

        saved = save_bundle(
            task_id="load_test",
            files=["src/app.py"],
            description="Load test bundle",
            base_path=tmp_path,
        )

        # Then load it
        loaded = load_bundle("load_test", base_path=tmp_path)

        assert loaded is not None
        assert loaded.task_id == saved.task_id
        assert loaded.description == saved.description
        assert loaded.file_count == 1

    def test_load_bundle_not_found(self, tmp_path: Path) -> None:
        """Return None for non-existent bundle."""
        result = load_bundle("nonexistent", base_path=tmp_path)

        assert result is None

    def test_load_compressed_bundle(self, tmp_path: Path) -> None:
        """Load a compressed bundle."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        bundle_data = {
            "task_id": "compressed_test",
            "created_at": "2026-01-31T12:00:00",
            "files": [],
            "description": "Compressed bundle",
            "total_lines": 0,
            "tags": [],
        }

        with gzip.open(bundles_dir / "compressed_test.json.gz", "wt") as f:
            json.dump(bundle_data, f)

        loaded = load_bundle("compressed_test", base_path=tmp_path)

        assert loaded is not None
        assert loaded.task_id == "compressed_test"
        assert loaded.description == "Compressed bundle"


class TestListBundles:
    """Tests for listing bundles."""

    def test_list_bundles_empty(self, tmp_path: Path) -> None:
        """List bundles when none exist."""
        bundles = list_bundles(base_path=tmp_path)

        assert bundles == []

    def test_list_bundles(self, tmp_path: Path) -> None:
        """List multiple bundles."""
        (tmp_path / "file.txt").write_text("content")

        save_bundle("bundle1", ["file.txt"], base_path=tmp_path)
        save_bundle("bundle2", ["file.txt"], base_path=tmp_path)
        save_bundle("bundle3", ["file.txt"], base_path=tmp_path)

        bundles = list_bundles(base_path=tmp_path)

        assert len(bundles) == 3

    def test_list_bundles_with_limit(self, tmp_path: Path) -> None:
        """List bundles with limit."""
        (tmp_path / "file.txt").write_text("content")

        for i in range(5):
            save_bundle(f"bundle{i}", ["file.txt"], base_path=tmp_path)

        bundles = list_bundles(base_path=tmp_path, limit=3)

        assert len(bundles) == 3

    def test_list_bundles_sorted_by_date(self, tmp_path: Path) -> None:
        """Bundles are sorted newest first."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create bundles with different dates
        for i, delta in enumerate([10, 5, 1]):
            data = {
                "task_id": f"bundle{i}",
                "created_at": (datetime.now() - timedelta(days=delta)).isoformat(),
                "files": [],
                "total_lines": 0,
                "tags": [],
            }
            (bundles_dir / f"bundle{i}.json").write_text(json.dumps(data))

        bundles = list_bundles(base_path=tmp_path)

        # Should be sorted newest first (delta=1, delta=5, delta=10)
        assert bundles[0].task_id == "bundle2"
        assert bundles[2].task_id == "bundle0"


class TestDiffBundles:
    """Tests for bundle diffing."""

    def test_diff_bundles(self, tmp_path: Path) -> None:
        """Diff two bundles."""
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.py").write_text("c")

        save_bundle("bundle1", ["a.py", "b.py"], base_path=tmp_path)
        save_bundle("bundle2", ["b.py", "c.py"], base_path=tmp_path)

        diff = diff_bundles("bundle1", "bundle2", base_path=tmp_path)

        assert diff is not None
        assert "a.py" in diff.removed
        assert "c.py" in diff.added
        assert "b.py" in diff.common

    def test_diff_bundles_not_found(self, tmp_path: Path) -> None:
        """Diff returns None if bundle not found."""
        diff = diff_bundles("nonexistent1", "nonexistent2", base_path=tmp_path)

        assert diff is None


class TestSuggestBundles:
    """Tests for bundle suggestion."""

    def test_suggest_bundles(self, tmp_path: Path) -> None:
        """Suggest bundles based on description."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create bundles with different descriptions
        bundles_data = [
            {
                "task_id": "auth_bundle",
                "created_at": datetime.now().isoformat(),
                "files": [{"path": "src/auth/login.py"}],
                "description": "Implement user authentication",
                "total_lines": 100,
                "tags": ["auth", "login"],
            },
            {
                "task_id": "api_bundle",
                "created_at": datetime.now().isoformat(),
                "files": [{"path": "src/api/routes.py"}],
                "description": "Add API endpoints",
                "total_lines": 200,
                "tags": ["api"],
            },
        ]

        for data in bundles_data:
            (bundles_dir / f"{data['task_id']}.json").write_text(
                json.dumps(data)
            )

        suggestions = suggest_bundles("auth login", base_path=tmp_path)

        assert len(suggestions) > 0
        assert suggestions[0][0].task_id == "auth_bundle"

    def test_suggest_bundles_empty(self, tmp_path: Path) -> None:
        """Suggest returns empty for no matches."""
        suggestions = suggest_bundles("something random", base_path=tmp_path)

        assert suggestions == []


class TestBundleFileContents:
    """Tests for loading bundle file contents."""

    def test_get_bundle_file_contents(self, tmp_path: Path) -> None:
        """Load file contents from bundle."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("def main():\n    print('hello')\n")

        bundle = save_bundle(
            "contents_test",
            ["src/main.py"],
            base_path=tmp_path,
        )

        contents = get_bundle_file_contents(bundle, base_path=tmp_path)

        assert "src/main.py" in contents
        assert "def main()" in contents["src/main.py"]

    def test_get_bundle_file_contents_missing_file(self, tmp_path: Path) -> None:
        """Handle missing files gracefully."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        bundle_data = {
            "task_id": "missing_contents",
            "created_at": datetime.now().isoformat(),
            "files": [{"path": "nonexistent.py", "lines_start": 1}],
            "total_lines": 0,
            "tags": [],
        }
        (bundles_dir / "missing_contents.json").write_text(json.dumps(bundle_data))

        bundle = load_bundle("missing_contents", base_path=tmp_path)
        contents = get_bundle_file_contents(bundle, base_path=tmp_path)

        assert contents == {}


class TestBundleCompression:
    """Tests for bundle compression."""

    def test_compress_old_bundles(self, tmp_path: Path) -> None:
        """Compress bundles older than threshold."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create an old bundle
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        old_bundle = {
            "task_id": "old_bundle",
            "created_at": old_date,
            "files": [],
            "total_lines": 0,
            "tags": [],
        }
        (bundles_dir / "old_bundle.json").write_text(json.dumps(old_bundle))

        # Create a new bundle
        new_bundle = {
            "task_id": "new_bundle",
            "created_at": datetime.now().isoformat(),
            "files": [],
            "total_lines": 0,
            "tags": [],
        }
        (bundles_dir / "new_bundle.json").write_text(json.dumps(new_bundle))

        count = compress_old_bundles(days=7, base_path=tmp_path)

        assert count == 1
        assert (bundles_dir / "old_bundle.json.gz").exists()
        assert not (bundles_dir / "old_bundle.json").exists()
        assert (bundles_dir / "new_bundle.json").exists()


class TestDeleteBundle:
    """Tests for bundle deletion."""

    def test_delete_bundle(self, tmp_path: Path) -> None:
        """Delete an existing bundle."""
        (tmp_path / "file.txt").write_text("content")
        save_bundle("delete_test", ["file.txt"], base_path=tmp_path)

        result = delete_bundle("delete_test", base_path=tmp_path)

        assert result is True
        assert not (tmp_path / ".adw" / "bundles" / "delete_test.json").exists()

    def test_delete_bundle_not_found(self, tmp_path: Path) -> None:
        """Delete returns False for non-existent bundle."""
        result = delete_bundle("nonexistent", base_path=tmp_path)

        assert result is False

    def test_delete_compressed_bundle(self, tmp_path: Path) -> None:
        """Delete a compressed bundle."""
        bundles_dir = tmp_path / ".adw" / "bundles"
        bundles_dir.mkdir(parents=True)

        bundle_data = {"task_id": "compressed", "created_at": datetime.now().isoformat()}
        with gzip.open(bundles_dir / "compressed.json.gz", "wt") as f:
            json.dump(bundle_data, f)

        result = delete_bundle("compressed", base_path=tmp_path)

        assert result is True
        assert not (bundles_dir / "compressed.json.gz").exists()
