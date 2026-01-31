#!/usr/bin/env python3
"""Demo script showing how to use the QUESTION message protocol.

This demonstrates the new agent → user question flow added in P1-001.
"""

from pathlib import Path
from adw.protocol.messages import (
    MessageType,
    write_question,
    write_answer,
    get_pending_questions,
    read_messages,
)


def demo_basic_question():
    """Demonstrate basic question/answer flow."""
    print("Demo: Basic Question Flow")
    print("-" * 60)

    # Simulated agent asks a question
    question_id = write_question(
        adw_id="demo001",
        question="What authentication method should we use?",
        context="Building user registration feature",
        options=["OAuth 2.0", "JWT", "Session-based"],
    )

    print(f"✓ Question created with ID: {question_id}")

    # Check pending questions (TUI would do this)
    pending = get_pending_questions("demo001")
    print(f"✓ Found {len(pending)} pending question(s)")

    for q in pending:
        print(f"\n  Question: {q.question}")
        print(f"  Context: {q.context}")
        print(f"  Options: {', '.join(q.options or [])}")

    # User answers the question
    write_answer("demo001", question_id, "JWT")
    print("\n✓ Answer submitted: JWT")

    # Verify no pending questions remain
    pending = get_pending_questions("demo001")
    print(f"✓ Pending questions remaining: {len(pending)}")

    print("\n" + "=" * 60)


def demo_multiple_questions():
    """Demonstrate handling multiple questions."""
    print("\nDemo: Multiple Questions")
    print("-" * 60)

    adw_id = "demo002"

    # Agent asks multiple questions
    q1 = write_question(
        adw_id,
        "Should we add input validation?",
        context="User form implementation",
    )
    q2 = write_question(
        adw_id,
        "Which CSS framework?",
        options=["Tailwind", "Bootstrap", "Custom"],
    )
    q3 = write_question(
        adw_id,
        "Enable dark mode support?",
    )

    print(f"✓ Created 3 questions")

    # Check all pending
    pending = get_pending_questions(adw_id)
    print(f"✓ Pending questions: {len(pending)}")

    # Answer them one by one
    write_answer(adw_id, q1, "Yes, add validation")
    print("✓ Answered question 1")

    pending = get_pending_questions(adw_id)
    print(f"  Pending: {len(pending)}")

    write_answer(adw_id, q2, "Tailwind")
    print("✓ Answered question 2")

    pending = get_pending_questions(adw_id)
    print(f"  Pending: {len(pending)}")

    write_answer(adw_id, q3, "Yes")
    print("✓ Answered question 3")

    pending = get_pending_questions(adw_id)
    print(f"  Pending: {len(pending)} (all answered)")

    print("\n" + "=" * 60)


def demo_message_types():
    """Show different message types in action."""
    print("\nDemo: Message Type Inspection")
    print("-" * 60)

    adw_id = "demo003"

    # Write different types of messages
    write_question(adw_id, "Use TypeScript?")

    # Read all messages and show types
    messages = read_messages(adw_id)

    for i, msg in enumerate(messages, 1):
        print(f"Message {i}:")
        print(f"  Type: {msg.message_type}")
        print(f"  Priority: {msg.priority}")
        if msg.message_type == MessageType.QUESTION and msg.question:
            print(f"  Question ID: {msg.question.id}")
            print(f"  Question: {msg.question.question}")

    print("\n" + "=" * 60)


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("QUESTION Message Protocol - Usage Examples")
    print("=" * 60 + "\n")

    demo_basic_question()
    demo_multiple_questions()
    demo_message_types()

    print("\n✅ Demo complete!\n")


if __name__ == "__main__":
    main()
