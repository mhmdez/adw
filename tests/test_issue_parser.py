"""Tests for GitHub issue template parsing.

Tests cover:
- YAML frontmatter parsing
- Markdown section parsing
- Inline tag extraction
- Label-based configuration
- Template merging with labels
- Full issue body parsing
"""

from __future__ import annotations

from adw.integrations.issue_parser import (
    IssueType,
    ParsedIssueTemplate,
    Priority,
    extract_config_from_labels,
    extract_inline_tags,
    merge_template_with_labels,
    parse_issue_body,
    parse_markdown_sections,
    parse_yaml_frontmatter,
)

# =============================================================================
# IssueType and Priority Enum Tests
# =============================================================================


class TestIssueType:
    """Tests for IssueType enum."""

    def test_issue_type_values(self) -> None:
        """Test all issue type values exist."""
        assert IssueType.BUG.value == "bug"
        assert IssueType.FEATURE.value == "feature"
        assert IssueType.REFACTOR.value == "refactor"
        assert IssueType.DOCS.value == "docs"
        assert IssueType.TEST.value == "test"
        assert IssueType.CHORE.value == "chore"
        assert IssueType.UNKNOWN.value == "unknown"


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_values(self) -> None:
        """Test all priority values exist."""
        assert Priority.P0.value == "p0"
        assert Priority.P1.value == "p1"
        assert Priority.P2.value == "p2"
        assert Priority.P3.value == "p3"


# =============================================================================
# ParsedIssueTemplate Tests
# =============================================================================


class TestParsedIssueTemplate:
    """Tests for ParsedIssueTemplate dataclass."""

    def test_default_values(self) -> None:
        """Test default template values."""
        template = ParsedIssueTemplate()

        assert template.issue_type == IssueType.UNKNOWN
        assert template.priority == Priority.P1
        assert template.workflow is None
        assert template.model is None
        assert template.tags == []

    def test_to_dict(self) -> None:
        """Test converting template to dictionary."""
        template = ParsedIssueTemplate(
            issue_type=IssueType.BUG,
            priority=Priority.P0,
            workflow="sdlc",
            model="opus",
            description="Test description",
        )
        data = template.to_dict()

        assert data["issue_type"] == "bug"
        assert data["priority"] == "p0"
        assert data["workflow"] == "sdlc"
        assert data["model"] == "opus"
        assert data["description"] == "Test description"

    def test_from_dict(self) -> None:
        """Test creating template from dictionary."""
        data = {
            "issue_type": "feature",
            "priority": "p2",
            "workflow": "standard",
            "model": "sonnet",
            "description": "Feature description",
            "tags": ["auth", "api"],
        }
        template = ParsedIssueTemplate.from_dict(data)

        assert template.issue_type == IssueType.FEATURE
        assert template.priority == Priority.P2
        assert template.workflow == "standard"
        assert template.model == "sonnet"
        assert template.description == "Feature description"
        assert template.tags == ["auth", "api"]

    def test_get_workflow_or_default_explicit(self) -> None:
        """Test getting explicitly set workflow."""
        template = ParsedIssueTemplate(workflow="sdlc")
        assert template.get_workflow_or_default() == "sdlc"

    def test_get_workflow_or_default_from_type(self) -> None:
        """Test deriving workflow from issue type."""
        # Bug -> bug-fix (focused bug fixing workflow)
        template = ParsedIssueTemplate(issue_type=IssueType.BUG)
        assert template.get_workflow_or_default() == "bug-fix"

        # Feature -> sdlc
        template = ParsedIssueTemplate(issue_type=IssueType.FEATURE)
        assert template.get_workflow_or_default() == "sdlc"

        # Docs -> simple
        template = ParsedIssueTemplate(issue_type=IssueType.DOCS)
        assert template.get_workflow_or_default() == "simple"

        # Chore -> simple
        template = ParsedIssueTemplate(issue_type=IssueType.CHORE)
        assert template.get_workflow_or_default() == "simple"

    def test_get_model_or_default_explicit(self) -> None:
        """Test getting explicitly set model."""
        template = ParsedIssueTemplate(model="opus")
        assert template.get_model_or_default() == "opus"

    def test_get_model_or_default_from_priority(self) -> None:
        """Test deriving model from priority."""
        # P0 -> opus
        template = ParsedIssueTemplate(priority=Priority.P0)
        assert template.get_model_or_default() == "opus"

        # P1 feature -> sonnet
        template = ParsedIssueTemplate(issue_type=IssueType.FEATURE, priority=Priority.P1)
        assert template.get_model_or_default() == "sonnet"

        # Docs -> haiku
        template = ParsedIssueTemplate(issue_type=IssueType.DOCS)
        assert template.get_model_or_default() == "haiku"

    def test_build_context_prompt_minimal(self) -> None:
        """Test minimal context prompt with just priority."""
        template = ParsedIssueTemplate()
        prompt = template.build_context_prompt()
        # Default template still includes priority
        assert "**Priority**: p1" in prompt

    def test_build_context_prompt_full(self) -> None:
        """Test full context prompt with all fields."""
        template = ParsedIssueTemplate(
            issue_type=IssueType.BUG,
            priority=Priority.P0,
            description="Login fails",
            context="Production environment",
            steps_to_reproduce="1. Click login\n2. Enter credentials",
            expected_behavior="User logged in",
            actual_behavior="Error message shown",
            affected_versions=["1.0.0", "1.1.0"],
            tags=["auth", "login"],
        )
        prompt = template.build_context_prompt()

        assert "## Issue Template Data" in prompt
        assert "**Issue Type**: bug" in prompt
        assert "**Priority**: p0" in prompt
        assert "**Description**:" in prompt
        assert "**Steps to Reproduce**:" in prompt
        assert "**Expected Behavior**:" in prompt
        assert "**Actual Behavior**:" in prompt
        assert "**Affected Versions**: 1.0.0, 1.1.0" in prompt
        assert "**Tags**: auth, login" in prompt


# =============================================================================
# YAML Frontmatter Parsing Tests
# =============================================================================


class TestParseYamlFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_no_frontmatter(self) -> None:
        """Test body without frontmatter."""
        body = "This is just regular text."
        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter == {}
        assert remaining == body

    def test_simple_frontmatter(self) -> None:
        """Test simple YAML frontmatter."""
        body = """---
type: bug
priority: p0
workflow: sdlc
---
Rest of body"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter["type"] == "bug"
        assert frontmatter["priority"] == "p0"
        assert frontmatter["workflow"] == "sdlc"
        assert remaining == "Rest of body"

    def test_frontmatter_with_lists(self) -> None:
        """Test frontmatter with list values."""
        body = """---
tags: [auth, security, api]
affected_versions: [1.0, 2.0]
---
Body text"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter["tags"] == ["auth", "security", "api"]
        assert frontmatter["affected_versions"] == ["1.0", "2.0"]

    def test_frontmatter_with_quoted_strings(self) -> None:
        """Test frontmatter with quoted values."""
        body = """---
description: "A quoted string"
name: 'Single quoted'
---
Body"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter["description"] == "A quoted string"
        assert frontmatter["name"] == "Single quoted"

    def test_frontmatter_with_booleans(self) -> None:
        """Test frontmatter with boolean values."""
        body = """---
urgent: true
skip_tests: false
enabled: yes
disabled: no
---
Body"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter["urgent"] is True
        assert frontmatter["skip_tests"] is False
        assert frontmatter["enabled"] is True
        assert frontmatter["disabled"] is False

    def test_unclosed_frontmatter(self) -> None:
        """Test body with unclosed frontmatter."""
        body = """---
type: bug
No closing delimiter"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter == {}
        assert remaining == body

    def test_empty_body(self) -> None:
        """Test empty body."""
        frontmatter, remaining = parse_yaml_frontmatter("")
        assert frontmatter == {}
        assert remaining == ""

    def test_frontmatter_with_comments(self) -> None:
        """Test frontmatter with comment lines."""
        body = """---
# This is a comment
type: bug
# Another comment
priority: p1
---
Body"""

        frontmatter, remaining = parse_yaml_frontmatter(body)

        assert frontmatter["type"] == "bug"
        assert frontmatter["priority"] == "p1"
        assert "#" not in frontmatter


# =============================================================================
# Markdown Section Parsing Tests
# =============================================================================


class TestParseMarkdownSections:
    """Tests for markdown section parsing."""

    def test_no_sections(self) -> None:
        """Test body without sections."""
        body = "Just plain text without headers."
        sections = parse_markdown_sections(body)
        assert sections == {}

    def test_single_section(self) -> None:
        """Test body with single section."""
        body = """## Description
This is the description content."""

        sections = parse_markdown_sections(body)

        assert "description" in sections
        assert sections["description"] == "This is the description content."

    def test_multiple_sections(self) -> None:
        """Test body with multiple sections."""
        body = """## Description
The description

## Steps to Reproduce
1. Do this
2. Do that

## Expected Behavior
It should work"""

        sections = parse_markdown_sections(body)

        assert len(sections) == 3
        assert "description" in sections
        assert "steps_to_reproduce" in sections
        assert "expected_behavior" in sections

    def test_h3_sections(self) -> None:
        """Test body with H3 headers."""
        body = """### Context
Some context here

### Notes
Additional notes"""

        sections = parse_markdown_sections(body)

        assert "context" in sections
        assert "notes" in sections

    def test_section_name_normalization(self) -> None:
        """Test that section names are normalized."""
        body = """## Steps To Reproduce
Steps here

## Expected-Behavior
Expected here"""

        sections = parse_markdown_sections(body)

        assert "steps_to_reproduce" in sections
        assert "expected_behavior" in sections


# =============================================================================
# Inline Tag Extraction Tests
# =============================================================================


class TestExtractInlineTags:
    """Tests for inline tag extraction."""

    def test_no_tags(self) -> None:
        """Test text without tags."""
        tags = extract_inline_tags("No tags here")
        assert tags == []

    def test_single_tag(self) -> None:
        """Test single tag extraction."""
        tags = extract_inline_tags("Task {opus} is complex")
        assert tags == ["opus"]

    def test_multiple_tags(self) -> None:
        """Test multiple tag extraction."""
        tags = extract_inline_tags("Complex {opus} {sdlc} task {p0}")
        assert tags == ["opus", "sdlc", "p0"]

    def test_tags_case_insensitive(self) -> None:
        """Test tags are lowercased."""
        tags = extract_inline_tags("Task {OPUS} {Sonnet} here")
        assert tags == ["opus", "sonnet"]

    def test_tags_with_hyphens(self) -> None:
        """Test tags with hyphens."""
        tags = extract_inline_tags("Add {feature-flag} support")
        assert tags == ["feature-flag"]

    def test_bug_fix_workflow_tag(self) -> None:
        """Test {bug-fix} workflow tag extraction."""
        tags = extract_inline_tags("Fix login issue {bug-fix}")
        assert tags == ["bug-fix"]

    def test_prototype_workflow_tag(self) -> None:
        """Test {prototype} workflow tag extraction."""
        tags = extract_inline_tags("Quick prototype {prototype} {haiku}")
        assert tags == ["prototype", "haiku"]


# =============================================================================
# Label Configuration Tests
# =============================================================================


class TestExtractConfigFromLabels:
    """Tests for label-based configuration extraction."""

    def test_empty_labels(self) -> None:
        """Test with no labels."""
        config = extract_config_from_labels([])
        assert config == {"workflow": None, "model": None, "priority": None, "type": None}

    def test_prefixed_labels(self) -> None:
        """Test prefixed label format (workflow:sdlc)."""
        labels = ["workflow:sdlc", "model:opus", "priority:p0", "type:bug"]
        config = extract_config_from_labels(labels)

        assert config["workflow"] == "sdlc"
        assert config["model"] == "opus"
        assert config["priority"] == "p0"
        assert config["type"] == "bug"

    def test_direct_labels(self) -> None:
        """Test direct label names (sdlc, opus)."""
        labels = ["sdlc", "opus", "p0", "bug"]
        config = extract_config_from_labels(labels)

        assert config["workflow"] == "sdlc"
        assert config["model"] == "opus"
        assert config["priority"] == "p0"
        assert config["type"] == "bug"

    def test_mixed_labels(self) -> None:
        """Test mix of prefixed and direct labels."""
        labels = ["workflow:standard", "haiku", "type:feature"]
        config = extract_config_from_labels(labels)

        assert config["workflow"] == "standard"
        assert config["model"] == "haiku"
        assert config["type"] == "feature"

    def test_unknown_labels_ignored(self) -> None:
        """Test that unknown labels are ignored."""
        labels = ["enhancement", "good-first-issue", "help-wanted"]
        config = extract_config_from_labels(labels)

        assert config == {"workflow": None, "model": None, "priority": None, "type": None}

    def test_case_insensitive(self) -> None:
        """Test labels are case-insensitive."""
        labels = ["WORKFLOW:SDLC", "Model:Opus"]
        config = extract_config_from_labels(labels)

        assert config["workflow"] == "sdlc"
        assert config["model"] == "opus"

    def test_bug_fix_workflow_label(self) -> None:
        """Test bug-fix workflow label."""
        labels = ["workflow:bug-fix"]
        config = extract_config_from_labels(labels)
        assert config["workflow"] == "bug-fix"

    def test_bugfix_alias_label(self) -> None:
        """Test bugfix alias is normalized to bug-fix."""
        labels = ["bugfix"]
        config = extract_config_from_labels(labels)
        assert config["workflow"] == "bug-fix"

    def test_prototype_workflow_label(self) -> None:
        """Test prototype workflow label."""
        labels = ["prototype"]
        config = extract_config_from_labels(labels)
        assert config["workflow"] == "prototype"

    def test_prefixed_prototype_workflow_label(self) -> None:
        """Test prefixed prototype workflow label."""
        labels = ["workflow:prototype"]
        config = extract_config_from_labels(labels)
        assert config["workflow"] == "prototype"


# =============================================================================
# Template Merging Tests
# =============================================================================


class TestMergeTemplateWithLabels:
    """Tests for merging template with labels."""

    def test_labels_override_template(self) -> None:
        """Test that labels override template values."""
        template = ParsedIssueTemplate(
            workflow="simple",
            model="haiku",
            priority=Priority.P2,
            issue_type=IssueType.DOCS,
        )
        labels = ["workflow:sdlc", "model:opus", "priority:p0", "type:bug"]

        result = merge_template_with_labels(template, labels)

        assert result.workflow == "sdlc"
        assert result.model == "opus"
        assert result.priority == Priority.P0
        assert result.issue_type == IssueType.BUG

    def test_labels_only_override_what_exists(self) -> None:
        """Test that partial labels only override matched fields."""
        template = ParsedIssueTemplate(
            workflow="standard",
            model="sonnet",
        )
        labels = ["opus"]  # Only override model

        result = merge_template_with_labels(template, labels)

        assert result.workflow == "standard"  # Unchanged
        assert result.model == "opus"  # Overridden

    def test_empty_labels_preserve_template(self) -> None:
        """Test that empty labels preserve template values."""
        template = ParsedIssueTemplate(
            workflow="sdlc",
            model="opus",
        )

        result = merge_template_with_labels(template, [])

        assert result.workflow == "sdlc"
        assert result.model == "opus"


# =============================================================================
# Full Issue Body Parsing Tests
# =============================================================================


class TestParseIssueBody:
    """Tests for full issue body parsing."""

    def test_parse_empty_body(self) -> None:
        """Test parsing empty body."""
        template = parse_issue_body("")
        assert template.issue_type == IssueType.UNKNOWN
        assert template.priority == Priority.P1

    def test_parse_frontmatter_only(self) -> None:
        """Test parsing body with only frontmatter."""
        body = """---
type: bug
priority: p0
workflow: sdlc
model: opus
tags: [auth, security]
---"""

        template = parse_issue_body(body)

        assert template.issue_type == IssueType.BUG
        assert template.priority == Priority.P0
        assert template.workflow == "sdlc"
        assert template.model == "opus"
        assert template.tags == ["auth", "security"]

    def test_parse_sections_only(self) -> None:
        """Test parsing body with only markdown sections."""
        body = """## Description
Login fails for users

## Steps to Reproduce
1. Click login
2. Enter credentials
3. Click submit

## Expected Behavior
User should be logged in

## Actual Behavior
Error message appears"""

        template = parse_issue_body(body)

        assert template.description == "Login fails for users"
        assert "Click login" in template.steps_to_reproduce
        assert "User should be logged in" in template.expected_behavior
        assert "Error message appears" in template.actual_behavior

    def test_parse_with_inline_tags(self) -> None:
        """Test parsing body with inline tags."""
        body = "This is a {bug} task that needs {opus}"
        title = "Fix critical {p0} issue"

        template = parse_issue_body(body, title)

        assert template.issue_type == IssueType.BUG
        assert template.model == "opus"
        assert template.priority == Priority.P0

    def test_parse_full_issue(self) -> None:
        """Test parsing complete issue body."""
        body = """---
type: bug
priority: p1
affected_versions: [1.0.0, 1.1.0]
---

## Description
Authentication fails intermittently.

## Steps to Reproduce
- Login with valid credentials
- Wait 5 minutes
- Try to access dashboard

## Expected Behavior
Dashboard loads successfully

## Actual Behavior
401 Unauthorized error"""

        template = parse_issue_body(body, "Auth bug")

        assert template.issue_type == IssueType.BUG
        assert template.priority == Priority.P1
        assert template.affected_versions == ["1.0.0", "1.1.0"]
        assert "Authentication fails" in template.description
        assert template.steps_to_reproduce is not None
        assert template.expected_behavior is not None
        assert template.actual_behavior is not None

    def test_parse_acceptance_criteria_as_list(self) -> None:
        """Test parsing acceptance criteria as list."""
        body = """## Acceptance Criteria
- Users can login with email
- Users can login with OAuth
- Invalid credentials show error"""

        template = parse_issue_body(body)

        assert len(template.acceptance_criteria) == 3
        assert "Users can login with email" in template.acceptance_criteria
        assert "Users can login with OAuth" in template.acceptance_criteria

    def test_inline_tags_override_frontmatter(self) -> None:
        """Test that inline tags can override frontmatter."""
        body = """---
workflow: simple
model: haiku
---
This needs {sdlc} and {opus}"""

        template = parse_issue_body(body)

        # Inline tags should override frontmatter
        assert template.workflow == "sdlc"
        assert template.model == "opus"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIssueParserIntegration:
    """Integration tests for issue parsing with labels."""

    def test_full_workflow_selection(self) -> None:
        """Test complete workflow selection from issue and labels."""
        body = """---
type: feature
---

## Description
Add dark mode support

## Acceptance Criteria
- Toggle in settings
- Persists across sessions"""

        template = parse_issue_body(body, "Dark mode {p0}")
        labels = ["enhancement", "workflow:sdlc"]

        template = merge_template_with_labels(template, labels)

        # Label workflow takes precedence
        assert template.workflow == "sdlc"
        # Inline tag p0 from title
        assert template.priority == Priority.P0
        # From frontmatter
        assert template.issue_type == IssueType.FEATURE
        # Default model for p0
        assert template.get_model_or_default() == "opus"

    def test_bug_template_workflow(self) -> None:
        """Test bug issue template flows to correct workflow."""
        body = """---
type: bug
priority: p0
---

## Steps to Reproduce
1. Click button

## Expected Behavior
It works

## Actual Behavior
It crashes"""

        template = parse_issue_body(body)

        # Bug defaults to bug-fix workflow (focused bug fixing)
        assert template.get_workflow_or_default() == "bug-fix"
        # P0 defaults to opus
        assert template.get_model_or_default() == "opus"

    def test_docs_template_workflow(self) -> None:
        """Test docs issue flows to simple workflow."""
        template = parse_issue_body("Update README", "Docs update")
        template.issue_type = IssueType.DOCS

        assert template.get_workflow_or_default() == "simple"
        assert template.get_model_or_default() == "haiku"
