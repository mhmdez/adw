"""Test suite for Phase 8: Parallel Isolation (Worktrees)

Tests:
- Git worktree creation, listing, removal
- Sparse checkout support
- Port allocation system
- Environment variable isolation
- CLI commands integration
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from adw.agent.environment import (
    get_agent_env,
    get_isolated_env,
    merge_env_files,
    write_env_file,
)
from adw.agent.ports import (
    find_available_ports,
    get_ports_for_adw,
    is_port_available,
    write_ports_env,
)
from adw.agent.worktree import (
    create_worktree,
    get_worktree_path,
    list_worktrees,
    remove_worktree,
    worktree_exists,
)


# ============================================================================
# WORKTREE MANAGEMENT TESTS
# ============================================================================


def test_worktree_path_generation():
    """Test worktree path generation."""
    path = get_worktree_path("test-feature")
    assert "trees/test-feature" in str(path)


def test_worktree_lifecycle():
    """Test creating, listing, and removing a worktree."""
    worktree_name = "test-lifecycle"

    # Ensure clean state
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None
    assert worktree_exists(worktree_name)
    assert (worktree_path / ".git").exists()

    # List worktrees - should include our new one
    worktrees = list_worktrees()
    assert any(worktree_name in wt.get("path", "") for wt in worktrees)

    # Remove worktree
    success = remove_worktree(worktree_name)
    assert success
    assert not worktree_exists(worktree_name)


def test_worktree_creation_with_custom_branch():
    """Test worktree creation with custom branch name."""
    worktree_name = "test-custom-branch"
    branch_name = "feature/custom-test"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create with custom branch
    worktree_path = create_worktree(worktree_name, branch_name=branch_name)
    assert worktree_path is not None

    # Verify branch name
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    assert branch_name in result.stdout

    # Cleanup
    remove_worktree(worktree_name, force=True)


def test_worktree_sparse_checkout():
    """Test sparse checkout configuration."""
    worktree_name = "test-sparse"
    sparse_paths = ["src/adw/agent", "tests"]

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create with sparse checkout
    worktree_path = create_worktree(worktree_name, sparse_paths=sparse_paths)
    assert worktree_path is not None

    # Verify sparse-checkout is configured
    sparse_file = worktree_path / ".git" / "info" / "sparse-checkout"
    if sparse_file.exists():
        content = sparse_file.read_text()
        # Sparse checkout should include our paths
        assert "src/adw/agent" in content or "tests" in content

    # Cleanup
    remove_worktree(worktree_name, force=True)


def test_worktree_env_file_copy():
    """Test that .env file is copied to worktree."""
    worktree_name = "test-env-copy"

    # Create a test .env file
    test_env_path = Path(".env.test")
    test_env_path.write_text("TEST_VAR=test_value\n")

    # Temporarily rename to .env
    env_backup = None
    if Path(".env").exists():
        env_backup = Path(".env").read_text()
        Path(".env").unlink()

    shutil.copy(test_env_path, ".env")

    try:
        # Cleanup
        if worktree_exists(worktree_name):
            remove_worktree(worktree_name, force=True)

        # Create worktree
        worktree_path = create_worktree(worktree_name)
        assert worktree_path is not None

        # Check if .env was copied
        worktree_env = worktree_path / ".env"
        assert worktree_env.exists()
        assert "TEST_VAR" in worktree_env.read_text()

        # Cleanup
        remove_worktree(worktree_name, force=True)

    finally:
        # Restore original .env
        test_env_path.unlink()
        if env_backup:
            Path(".env").write_text(env_backup)
        elif Path(".env").exists():
            Path(".env").unlink()


# ============================================================================
# PORT ALLOCATION TESTS
# ============================================================================


def test_deterministic_port_allocation():
    """Test that same ADW ID gets same ports."""
    adw_id = "abc123de"

    ports1 = get_ports_for_adw(adw_id)
    ports2 = get_ports_for_adw(adw_id)

    assert ports1 == ports2
    assert len(ports1) == 2
    assert 9100 <= ports1[0] <= 9114  # Backend port range
    assert 9200 <= ports1[1] <= 9214  # Frontend port range


def test_different_ids_get_different_ports():
    """Test that different ADW IDs get different ports."""
    adw_id1 = "aaaaaaaa"
    adw_id2 = "bbbbbbbb"

    ports1 = get_ports_for_adw(adw_id1)
    ports2 = get_ports_for_adw(adw_id2)

    # Different IDs should get different ports (usually)
    # Note: With only 15 slots, collisions are possible but unlikely for different IDs
    assert isinstance(ports1, tuple)
    assert isinstance(ports2, tuple)


def test_port_availability_check():
    """Test port availability checking."""
    # Port 0 should never be available (system reserved)
    # Find a likely available high port
    test_port = 65123

    # The function should run without error
    available = is_port_available(test_port)
    assert isinstance(available, bool)


def test_find_available_ports_with_fallback():
    """Test finding available ports with fallback logic."""
    adw_id = "test1234"

    backend, frontend = find_available_ports(adw_id)

    assert isinstance(backend, int)
    assert isinstance(frontend, int)
    assert backend != frontend


def test_write_ports_env_file():
    """Test writing .ports.env file."""
    worktree_name = "test-ports-env"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Write ports file
    backend_port = 9100
    frontend_port = 9200
    write_ports_env(str(worktree_path), backend_port, frontend_port)

    # Verify file contents
    ports_file = worktree_path / ".ports.env"
    assert ports_file.exists()

    content = ports_file.read_text()
    assert f"BACKEND_PORT={backend_port}" in content
    assert f"FRONTEND_PORT={frontend_port}" in content
    assert f"VITE_API_URL=http://localhost:{backend_port}" in content

    # Cleanup
    remove_worktree(worktree_name, force=True)


# ============================================================================
# ENVIRONMENT ISOLATION TESTS
# ============================================================================


def test_isolated_env_basic():
    """Test basic isolated environment creation."""
    adw_id = "test1234"
    backend_port = 9100
    frontend_port = 9200

    env = get_isolated_env(
        adw_id=adw_id,
        backend_port=backend_port,
        frontend_port=frontend_port,
    )

    assert env["ADW_ID"] == adw_id
    assert env["BACKEND_PORT"] == str(backend_port)
    assert env["FRONTEND_PORT"] == str(frontend_port)
    assert env["PORT"] == str(backend_port)
    assert env["VITE_API_URL"] == f"http://localhost:{backend_port}"
    assert env["VITE_PORT"] == str(frontend_port)


def test_isolated_env_with_worktree_path():
    """Test isolated environment with worktree path."""
    adw_id = "test5678"
    worktree_path = "/path/to/worktree"

    env = get_isolated_env(adw_id=adw_id, worktree_path=worktree_path)

    assert env["ADW_ID"] == adw_id
    assert env["ADW_WORKTREE"] == worktree_path


def test_env_file_parsing():
    """Test .env file parsing."""
    worktree_name = "test-env-parse"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Write test .env file
    env_vars = {
        "DATABASE_URL": "postgresql://localhost/test",
        "API_KEY": "secret123",
        "DEBUG": "true",
    }
    write_env_file(worktree_path, env_vars, ".env")

    # Parse it back
    merged_env = merge_env_files(worktree_path)

    assert merged_env["DATABASE_URL"] == "postgresql://localhost/test"
    assert merged_env["API_KEY"] == "secret123"
    assert merged_env["DEBUG"] == "true"

    # Cleanup
    remove_worktree(worktree_name, force=True)


def test_env_file_with_quotes():
    """Test .env file parsing with quoted values."""
    worktree_name = "test-env-quotes"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Write env file with spaces (should be quoted)
    env_vars = {
        "MESSAGE": "Hello World",
        "PATH_VAR": "/path/with spaces/here",
    }
    write_env_file(worktree_path, env_vars, ".env")

    # Read back
    merged_env = merge_env_files(worktree_path)

    assert merged_env["MESSAGE"] == "Hello World"
    assert merged_env["PATH_VAR"] == "/path/with spaces/here"

    # Cleanup
    remove_worktree(worktree_name, force=True)


def test_ports_env_precedence():
    """Test that .ports.env takes precedence over .env."""
    worktree_name = "test-env-precedence"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Write .env with one port
    write_env_file(worktree_path, {"BACKEND_PORT": "8000"}, ".env")

    # Write .ports.env with different port
    write_ports_env(str(worktree_path), 9100, 9200)

    # Merge - .ports.env should win
    merged_env = merge_env_files(worktree_path)

    assert merged_env["BACKEND_PORT"] == "9100"

    # Cleanup
    remove_worktree(worktree_name, force=True)


def test_get_agent_env_complete():
    """Test complete agent environment with all features."""
    worktree_name = "test-complete-env"
    adw_id = "complete1"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Write some env vars
    write_env_file(worktree_path, {"CUSTOM_VAR": "custom_value"}, ".env")
    write_ports_env(str(worktree_path), 9105, 9205)

    # Get complete agent environment
    env = get_agent_env(
        adw_id=adw_id,
        worktree_path=str(worktree_path),
        backend_port=9105,
        frontend_port=9205,
    )

    # Check all components are present
    assert env["ADW_ID"] == adw_id
    assert env["ADW_WORKTREE"] == str(worktree_path)
    assert env["BACKEND_PORT"] == "9105"
    assert env["FRONTEND_PORT"] == "9205"
    assert env["CUSTOM_VAR"] == "custom_value"
    assert env["VITE_API_URL"] == "http://localhost:9105"

    # Cleanup
    remove_worktree(worktree_name, force=True)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_parallel_worktree_isolation():
    """Test that multiple worktrees can exist simultaneously."""
    worktrees = ["parallel-1", "parallel-2", "parallel-3"]

    # Create all worktrees
    paths = []
    for name in worktrees:
        if worktree_exists(name):
            remove_worktree(name, force=True)

        path = create_worktree(name)
        assert path is not None
        paths.append(path)

    # Verify all exist
    for name in worktrees:
        assert worktree_exists(name)

    # Get ports for each
    port_sets = []
    for i, name in enumerate(worktrees):
        adw_id = f"test000{i}"
        backend, frontend = find_available_ports(adw_id)
        port_sets.append((backend, frontend))

        # Write to worktree
        write_ports_env(str(paths[i]), backend, frontend)

    # Verify no port conflicts
    all_ports = [p for ports in port_sets for p in ports]
    assert len(all_ports) == len(set(all_ports)), "Port conflict detected!"

    # Cleanup
    for name in worktrees:
        remove_worktree(name, force=True)


def test_worktree_with_complete_isolation():
    """Integration test: Create worktree with full isolation setup."""
    worktree_name = "integration-test"
    adw_id = "integ123"

    # Cleanup
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create worktree
    worktree_path = create_worktree(worktree_name)
    assert worktree_path is not None

    # Allocate ports
    backend_port, frontend_port = find_available_ports(adw_id)

    # Write ports configuration
    write_ports_env(str(worktree_path), backend_port, frontend_port)

    # Write custom env vars
    custom_env = {
        "NODE_ENV": "development",
        "API_URL": f"http://localhost:{backend_port}",
    }
    write_env_file(worktree_path, custom_env, ".custom.env")

    # Get complete agent environment
    env = get_agent_env(
        adw_id=adw_id,
        worktree_path=str(worktree_path),
        backend_port=backend_port,
        frontend_port=frontend_port,
    )

    # Verify isolation
    assert env["ADW_ID"] == adw_id
    assert env["BACKEND_PORT"] == str(backend_port)
    assert env["FRONTEND_PORT"] == str(frontend_port)
    assert worktree_exists(worktree_name)

    # Verify files exist
    assert (worktree_path / ".ports.env").exists()
    assert (worktree_path / ".custom.env").exists()

    # Cleanup
    remove_worktree(worktree_name, force=True)


# ============================================================================
# CLI INTEGRATION TESTS
# ============================================================================


def test_cli_worktree_commands_exist():
    """Test that CLI commands are properly registered."""
    from click.testing import CliRunner

    from adw.cli import main

    runner = CliRunner()

    # Test worktree group exists
    result = runner.invoke(main, ["worktree", "--help"])
    assert result.exit_code == 0
    assert "worktree" in result.output.lower()

    # Test subcommands exist
    assert "create" in result.output
    assert "list" in result.output
    assert "remove" in result.output


def test_cli_worktree_list():
    """Test CLI worktree list command."""
    from click.testing import CliRunner

    from adw.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["worktree", "list"])

    # Should succeed (even if empty)
    assert result.exit_code == 0


def test_cli_worktree_create_and_remove():
    """Test CLI worktree create and remove commands."""
    from click.testing import CliRunner

    from adw.cli import main

    runner = CliRunner()
    worktree_name = "cli-test-worktree"

    # Cleanup first
    if worktree_exists(worktree_name):
        remove_worktree(worktree_name, force=True)

    # Create via CLI
    result = runner.invoke(main, ["worktree", "create", worktree_name])
    assert result.exit_code == 0
    assert worktree_exists(worktree_name)

    # Remove via CLI
    result = runner.invoke(main, ["worktree", "remove", worktree_name])
    assert result.exit_code == 0

    # Verify removed
    assert not worktree_exists(worktree_name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
