#!/usr/bin/env python3
"""Test Phase 6: Message Injection functionality.

This test verifies:
1. Message protocol models work correctly
2. Messages can be written to agent message files
3. Messages can be read back correctly
4. The check_messages.py hook works correctly
5. Priority system works (normal, high, interrupt)
"""

import json
import tempfile
from pathlib import Path
import subprocess
import sys

from adw.protocol.messages import (
    AgentMessage,
    MessagePriority,
    write_message,
    read_messages,
    read_unprocessed_messages,
)


def test_message_models():
    """Test AgentMessage model serialization."""
    print("Testing message models...")

    msg = AgentMessage(message="Test message", priority=MessagePriority.NORMAL)

    # Test JSONL serialization
    jsonl = msg.to_jsonl()
    assert isinstance(jsonl, str)

    # Test deserialization
    msg2 = AgentMessage.from_jsonl(jsonl)
    assert msg2.message == "Test message"
    assert msg2.priority == MessagePriority.NORMAL

    print("✓ Message models work correctly")


def test_write_and_read_messages():
    """Test writing and reading messages."""
    print("\nTesting write and read messages...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        adw_id = "test123abc"

        # Write messages
        write_message(adw_id, "First message", MessagePriority.NORMAL, project_dir)
        write_message(adw_id, "Second message", MessagePriority.HIGH, project_dir)
        write_message(adw_id, "STOP NOW", MessagePriority.NORMAL, project_dir)  # Auto-detects interrupt

        # Read messages back
        messages = read_messages(adw_id, project_dir)

        assert len(messages) == 3
        assert messages[0].message == "First message"
        assert messages[0].priority == MessagePriority.NORMAL
        assert messages[1].message == "Second message"
        assert messages[1].priority == MessagePriority.HIGH
        assert messages[2].message == "STOP NOW"
        assert messages[2].priority == MessagePriority.INTERRUPT  # Auto-detected

        # Verify file structure
        messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
        assert messages_file.exists()

        print("✓ Write and read messages work correctly")


def test_unprocessed_messages():
    """Test unprocessed message tracking."""
    print("\nTesting unprocessed message tracking...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        adw_id = "test456def"

        # Write messages
        write_message(adw_id, "Message 1", project_dir=project_dir)
        write_message(adw_id, "Message 2", project_dir=project_dir)

        # First read - should get both messages
        unprocessed = list(read_unprocessed_messages(adw_id, project_dir))
        assert len(unprocessed) == 2
        assert unprocessed[0].message == "Message 1"
        assert unprocessed[1].message == "Message 2"

        # Second read - should get no messages (already processed)
        unprocessed = list(read_unprocessed_messages(adw_id, project_dir))
        assert len(unprocessed) == 0

        # Add new message
        write_message(adw_id, "Message 3", project_dir=project_dir)

        # Third read - should get only new message
        unprocessed = list(read_unprocessed_messages(adw_id, project_dir))
        assert len(unprocessed) == 1
        assert unprocessed[0].message == "Message 3"

        # Verify processed file exists
        processed_file = project_dir / "agents" / adw_id / "adw_messages_processed.jsonl"
        assert processed_file.exists()

        print("✓ Unprocessed message tracking works correctly")


def test_check_messages_hook():
    """Test the check_messages.py hook script."""
    print("\nTesting check_messages.py hook...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        adw_id = "test789ghi"

        # Write a test message
        write_message(adw_id, "Hello from user!", MessagePriority.NORMAL, project_dir)

        # Run the hook script
        env = {
            "ADW_ID": adw_id,
            "CLAUDE_PROJECT_DIR": str(project_dir),
        }

        result = subprocess.run(
            ["python3", ".claude/hooks/check_messages.py"],
            capture_output=True,
            text=True,
            env={**env},
        )

        # Should succeed
        assert result.returncode == 0

        # Should output the message
        assert "MESSAGE FROM USER" in result.stdout
        assert "Hello from user!" in result.stdout

        # Run again - should not show message (already processed)
        result = subprocess.run(
            ["python3", ".claude/hooks/check_messages.py"],
            capture_output=True,
            text=True,
            env={**env},
        )

        assert result.returncode == 0
        assert "MESSAGE FROM USER" not in result.stdout

        print("✓ check_messages.py hook works correctly")


def test_priority_system():
    """Test message priority detection and handling."""
    print("\nTesting priority system...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        adw_id = "testpriority"

        # Test auto-detection of STOP commands
        write_message(adw_id, "STOP working on this", project_dir=project_dir)
        write_message(adw_id, "stop this task", project_dir=project_dir)
        write_message(adw_id, "Normal message", project_dir=project_dir)

        messages = read_messages(adw_id, project_dir)

        assert messages[0].priority == MessagePriority.INTERRUPT  # STOP detected
        assert messages[1].priority == MessagePriority.INTERRUPT  # stop detected
        assert messages[2].priority == MessagePriority.NORMAL

        # Test hook output for interrupt priority
        env = {
            "ADW_ID": adw_id,
            "CLAUDE_PROJECT_DIR": str(project_dir),
        }

        result = subprocess.run(
            ["python3", ".claude/hooks/check_messages.py"],
            capture_output=True,
            text=True,
            env={**env},
        )

        assert "HIGH PRIORITY" in result.stdout

        print("✓ Priority system works correctly")


def test_message_file_format():
    """Test that message files use correct JSONL format."""
    print("\nTesting message file format...")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        adw_id = "testformat"

        write_message(adw_id, "Test message", project_dir=project_dir)

        messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
        content = messages_file.read_text()

        # Should be valid JSONL (one JSON object per line)
        lines = content.strip().split("\n")
        for line in lines:
            obj = json.loads(line)  # Should not raise
            assert "message" in obj
            assert "priority" in obj
            assert "timestamp" in obj

        print("✓ Message file format is correct JSONL")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 6: Message Injection - Verification Tests")
    print("=" * 60)

    try:
        test_message_models()
        test_write_and_read_messages()
        test_unprocessed_messages()
        test_check_messages_hook()
        test_priority_system()
        test_message_file_format()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Phase 6 is working correctly!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
