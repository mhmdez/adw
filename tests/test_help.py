"""Tests for help and examples system."""

from __future__ import annotations

import pytest

from adw.help import (
    EXAMPLES,
    Category,
    Complexity,
    Example,
    format_category_name,
    format_complexity_name,
    get_category_summary,
    get_examples_by_category,
    get_examples_by_complexity,
    iter_examples,
    search_examples,
)


# =============================================================================
# Example Dataclass Tests
# =============================================================================


class TestExample:
    """Tests for Example dataclass."""

    def test_example_creation(self) -> None:
        """Test creating an Example."""
        example = Example(
            title="Test Example",
            description="A test description",
            commands=["cmd1", "cmd2"],
            category=Category.QUICKSTART,
            complexity=Complexity.BEGINNER,
        )
        assert example.title == "Test Example"
        assert example.description == "A test description"
        assert len(example.commands) == 2
        assert example.category == Category.QUICKSTART
        assert example.complexity == Complexity.BEGINNER
        assert example.notes == []
        assert example.related == []

    def test_example_with_notes_and_related(self) -> None:
        """Test Example with optional fields."""
        example = Example(
            title="Full Example",
            description="Complete example",
            commands=["cmd"],
            category=Category.TASKS,
            complexity=Complexity.INTERMEDIATE,
            notes=["Note 1", "Note 2"],
            related=["cmd1", "cmd2"],
        )
        assert len(example.notes) == 2
        assert len(example.related) == 2
        assert "Note 1" in example.notes
        assert "cmd1" in example.related

    def test_example_format_basic(self) -> None:
        """Test basic formatting."""
        example = Example(
            title="Format Test",
            description="Testing format",
            commands=["adw test"],
            category=Category.QUICKSTART,
            complexity=Complexity.BEGINNER,
        )
        output = example.format()
        assert "Format Test" in output
        assert "Testing format" in output
        assert "$ adw test" in output

    def test_example_format_verbose(self) -> None:
        """Test verbose formatting includes notes."""
        example = Example(
            title="Verbose Test",
            description="Testing verbose",
            commands=["cmd"],
            category=Category.QUICKSTART,
            complexity=Complexity.BEGINNER,
            notes=["Important note"],
            related=["other-cmd"],
        )
        output = example.format(verbose=True)
        assert "Important note" in output
        assert "other-cmd" in output

    def test_example_format_non_verbose_hides_notes(self) -> None:
        """Test non-verbose formatting hides notes."""
        example = Example(
            title="Non-verbose Test",
            description="Testing non-verbose",
            commands=["cmd"],
            category=Category.QUICKSTART,
            complexity=Complexity.BEGINNER,
            notes=["Hidden note"],
        )
        output = example.format(verbose=False)
        assert "Hidden note" not in output


# =============================================================================
# Category Enum Tests
# =============================================================================


class TestCategory:
    """Tests for Category enum."""

    def test_category_values(self) -> None:
        """Test all category values exist."""
        assert Category.QUICKSTART.value == "quickstart"
        assert Category.TASKS.value == "tasks"
        assert Category.WORKFLOWS.value == "workflows"
        assert Category.GITHUB.value == "github"
        assert Category.MONITORING.value == "monitoring"
        assert Category.PARALLEL.value == "parallel"
        assert Category.CONFIG.value == "config"
        assert Category.INTEGRATIONS.value == "integrations"

    def test_category_count(self) -> None:
        """Test expected number of categories."""
        assert len(Category) == 8


# =============================================================================
# Complexity Enum Tests
# =============================================================================


class TestComplexity:
    """Tests for Complexity enum."""

    def test_complexity_values(self) -> None:
        """Test all complexity values exist."""
        assert Complexity.BEGINNER.value == "beginner"
        assert Complexity.INTERMEDIATE.value == "intermediate"
        assert Complexity.ADVANCED.value == "advanced"

    def test_complexity_count(self) -> None:
        """Test expected number of complexity levels."""
        assert len(Complexity) == 3


# =============================================================================
# Filter Function Tests
# =============================================================================


class TestGetExamplesByCategory:
    """Tests for get_examples_by_category function."""

    def test_quickstart_category(self) -> None:
        """Test filtering quickstart examples."""
        examples = get_examples_by_category(Category.QUICKSTART)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.category == Category.QUICKSTART

    def test_tasks_category(self) -> None:
        """Test filtering tasks examples."""
        examples = get_examples_by_category(Category.TASKS)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.category == Category.TASKS

    def test_workflows_category(self) -> None:
        """Test filtering workflows examples."""
        examples = get_examples_by_category(Category.WORKFLOWS)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.category == Category.WORKFLOWS

    def test_github_category(self) -> None:
        """Test filtering github examples."""
        examples = get_examples_by_category(Category.GITHUB)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.category == Category.GITHUB

    def test_all_categories_have_examples(self) -> None:
        """Test every category has at least one example."""
        for category in Category:
            examples = get_examples_by_category(category)
            assert len(examples) >= 1, f"Category {category} has no examples"


class TestGetExamplesByComplexity:
    """Tests for get_examples_by_complexity function."""

    def test_beginner_complexity(self) -> None:
        """Test filtering beginner examples."""
        examples = get_examples_by_complexity(Complexity.BEGINNER)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.complexity == Complexity.BEGINNER

    def test_intermediate_complexity(self) -> None:
        """Test filtering intermediate examples."""
        examples = get_examples_by_complexity(Complexity.INTERMEDIATE)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.complexity == Complexity.INTERMEDIATE

    def test_advanced_complexity(self) -> None:
        """Test filtering advanced examples."""
        examples = get_examples_by_complexity(Complexity.ADVANCED)
        assert len(examples) >= 1
        for ex in examples:
            assert ex.complexity == Complexity.ADVANCED

    def test_all_complexities_have_examples(self) -> None:
        """Test every complexity level has at least one example."""
        for complexity in Complexity:
            examples = get_examples_by_complexity(complexity)
            assert len(examples) >= 1, f"Complexity {complexity} has no examples"


# =============================================================================
# Search Function Tests
# =============================================================================


class TestSearchExamples:
    """Tests for search_examples function."""

    def test_search_by_title(self) -> None:
        """Test searching by title keyword."""
        results = search_examples("initialize")
        assert len(results) >= 1
        assert any("Initialize" in r.title for r in results)

    def test_search_by_description(self) -> None:
        """Test searching by description keyword."""
        results = search_examples("autonomous")
        assert len(results) >= 1

    def test_search_by_command(self) -> None:
        """Test searching by command content."""
        results = search_examples("adw init")
        assert len(results) >= 1

    def test_search_case_insensitive(self) -> None:
        """Test search is case insensitive."""
        lower_results = search_examples("github")
        upper_results = search_examples("GITHUB")
        assert len(lower_results) == len(upper_results)

    def test_search_no_results(self) -> None:
        """Test search with no matches."""
        results = search_examples("xyznonexistentquery123")
        assert len(results) == 0

    def test_search_partial_match(self) -> None:
        """Test search with partial keyword."""
        results = search_examples("work")  # Should match workflow, worktree
        assert len(results) >= 1


# =============================================================================
# Summary Function Tests
# =============================================================================


class TestGetCategorySummary:
    """Tests for get_category_summary function."""

    def test_summary_has_all_categories(self) -> None:
        """Test summary includes all categories."""
        summary = get_category_summary()
        assert len(summary) == len(Category)
        for category in Category:
            assert category in summary

    def test_summary_counts_are_positive(self) -> None:
        """Test all counts are positive."""
        summary = get_category_summary()
        for category, count in summary.items():
            assert count >= 0, f"Category {category} has negative count"

    def test_summary_matches_filter(self) -> None:
        """Test summary counts match filter function."""
        summary = get_category_summary()
        for category in Category:
            filtered = get_examples_by_category(category)
            assert summary[category] == len(filtered)


# =============================================================================
# Iterator Function Tests
# =============================================================================


class TestIterExamples:
    """Tests for iter_examples function."""

    def test_iter_yields_examples(self) -> None:
        """Test iterator yields Example objects."""
        examples = list(iter_examples())
        assert len(examples) > 0
        for ex in examples:
            assert isinstance(ex, Example)

    def test_iter_matches_catalog(self) -> None:
        """Test iterator matches EXAMPLES catalog."""
        examples = list(iter_examples())
        assert len(examples) == len(EXAMPLES)


# =============================================================================
# Format Function Tests
# =============================================================================


class TestFormatCategoryName:
    """Tests for format_category_name function."""

    def test_quickstart_format(self) -> None:
        """Test quickstart category formatting."""
        assert format_category_name(Category.QUICKSTART) == "Quick Start"

    def test_tasks_format(self) -> None:
        """Test tasks category formatting."""
        assert format_category_name(Category.TASKS) == "Task Management"

    def test_github_format(self) -> None:
        """Test github category formatting."""
        assert format_category_name(Category.GITHUB) == "GitHub Integration"

    def test_all_categories_have_names(self) -> None:
        """Test all categories have formatted names."""
        for category in Category:
            name = format_category_name(category)
            assert name is not None
            assert len(name) > 0


class TestFormatComplexityName:
    """Tests for format_complexity_name function."""

    def test_beginner_format(self) -> None:
        """Test beginner complexity formatting."""
        result = format_complexity_name(Complexity.BEGINNER)
        assert "Beginner" in result
        assert "green" in result

    def test_intermediate_format(self) -> None:
        """Test intermediate complexity formatting."""
        result = format_complexity_name(Complexity.INTERMEDIATE)
        assert "Intermediate" in result
        assert "yellow" in result

    def test_advanced_format(self) -> None:
        """Test advanced complexity formatting."""
        result = format_complexity_name(Complexity.ADVANCED)
        assert "Advanced" in result
        assert "red" in result


# =============================================================================
# Catalog Validation Tests
# =============================================================================


class TestExamplesCatalog:
    """Tests for the EXAMPLES catalog integrity."""

    def test_catalog_not_empty(self) -> None:
        """Test catalog has examples."""
        assert len(EXAMPLES) > 0

    def test_catalog_has_minimum_examples(self) -> None:
        """Test catalog has sufficient examples."""
        assert len(EXAMPLES) >= 20  # Reasonable minimum

    def test_all_examples_have_required_fields(self) -> None:
        """Test all examples have required fields."""
        for example in EXAMPLES:
            assert example.title, f"Example missing title"
            assert example.description, f"Example '{example.title}' missing description"
            assert len(example.commands) > 0, f"Example '{example.title}' has no commands"
            assert example.category is not None
            assert example.complexity is not None

    def test_all_examples_have_valid_category(self) -> None:
        """Test all examples have valid category."""
        for example in EXAMPLES:
            assert example.category in Category, f"Example '{example.title}' has invalid category"

    def test_all_examples_have_valid_complexity(self) -> None:
        """Test all examples have valid complexity."""
        for example in EXAMPLES:
            assert (
                example.complexity in Complexity
            ), f"Example '{example.title}' has invalid complexity"

    def test_example_titles_are_unique(self) -> None:
        """Test all example titles are unique."""
        titles = [ex.title for ex in EXAMPLES]
        assert len(titles) == len(set(titles)), "Duplicate example titles found"

    def test_commands_not_empty_strings(self) -> None:
        """Test no example has empty command strings."""
        for example in EXAMPLES:
            for cmd in example.commands:
                assert cmd.strip(), f"Example '{example.title}' has empty command"

    def test_descriptions_reasonable_length(self) -> None:
        """Test descriptions are reasonable length."""
        for example in EXAMPLES:
            assert len(example.description) >= 10, f"Example '{example.title}' description too short"
            assert (
                len(example.description) <= 200
            ), f"Example '{example.title}' description too long"


# =============================================================================
# Coverage Tests
# =============================================================================


class TestExamplesCoverage:
    """Tests for adequate coverage of features."""

    def test_has_init_example(self) -> None:
        """Test there's an init example."""
        results = search_examples("init")
        assert len(results) >= 1

    def test_has_run_example(self) -> None:
        """Test there's a run example."""
        results = search_examples("run")
        assert len(results) >= 1

    def test_has_github_examples(self) -> None:
        """Test there are GitHub examples."""
        examples = get_examples_by_category(Category.GITHUB)
        assert len(examples) >= 2

    def test_has_workflow_examples(self) -> None:
        """Test there are workflow examples."""
        examples = get_examples_by_category(Category.WORKFLOWS)
        assert len(examples) >= 2

    def test_has_beginner_examples(self) -> None:
        """Test there are beginner examples."""
        examples = get_examples_by_complexity(Complexity.BEGINNER)
        assert len(examples) >= 5  # At least 5 beginner examples

    def test_has_dashboard_example(self) -> None:
        """Test there's a dashboard example."""
        results = search_examples("dashboard")
        assert len(results) >= 1

    def test_has_config_examples(self) -> None:
        """Test there are config examples."""
        examples = get_examples_by_category(Category.CONFIG)
        assert len(examples) >= 2
