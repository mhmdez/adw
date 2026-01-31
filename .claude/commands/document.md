# /document - Generate documentation

Generate comprehensive documentation for completed and reviewed implementation.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Generate documentation
model: sonnet
```

## Purpose

Create comprehensive documentation after implementation, testing, and code review phases. This phase focuses on generating user-facing documentation, API references, usage examples, and updating project documentation to reflect new features.

## When to Use

- After completing implementation with `/implement`, testing with `/test`, and review with `/review`
- Following SDLC workflow after review phase
- When a feature needs user-facing documentation
- For documenting API changes or new functionality

## Input

$ARGUMENTS - Spec file path, task description, or empty for most recent reviewed implementation

- **Spec file**: `specs/feature-name.md`
- **Task description**: "Document user authentication system"
- **Empty**: Documents the most recently reviewed feature

## Process

### 1. Load Implementation Context

- Read the spec file from `specs/` (if available)
- Identify all files created or modified in implementation
- Review the feature's requirements and functionality
- Check existing documentation structure and conventions
- Note project documentation standards (README, docs/, etc.)

### 2. Create Todo List

Use TodoWrite to track documentation tasks:
- Update README.md (if needed)
- Create/update API documentation
- Add usage examples
- Update configuration guides
- Create migration guides (if applicable)
- Update changelog
- Mark initial task as in_progress

### 3. Understand Documentation Patterns

Explore existing documentation structure:

```bash
# Find documentation files
ls docs/
ls *.md
```

Use Read/Glob to understand:
- Documentation file organization
- Writing style and tone
- Example code patterns
- Formatting conventions
- Link structure

### 4. Update README.md

If the feature impacts user-facing functionality:

**Add to README**:
- Feature description in overview
- Installation/setup changes (if any)
- Basic usage examples
- Link to detailed documentation
- Update table of contents

**Keep README focused**:
- High-level overview only
- Common use cases
- Quick start examples
- Links to detailed docs

### 5. Create Feature Documentation

Create detailed documentation in `docs/` directory:

**Structure**:
```markdown
# {Feature Name}

## Overview

{What this feature does and why it exists}

## Installation

{Any setup or installation steps required}

## Basic Usage

{Simple example showing common use case}

```{language}
# Code example
```

## API Reference

### {Function/Class Name}

**Description**: {What it does}

**Parameters**:
- `param1` ({type}): {description}
- `param2` ({type}, optional): {description}

**Returns**: {return type} - {description}

**Raises**:
- `ExceptionType`: {when this is raised}

**Example**:
```{language}
# Example usage
```

## Configuration

{Configuration options and settings}

### Environment Variables

- `ENV_VAR_NAME`: {description} (default: {value})

### Config File

```yaml
# Example configuration
```

## Advanced Usage

{Complex use cases and patterns}

### {Scenario Name}

{Description and example}

## Examples

### {Example Name}

{Description of what this example demonstrates}

```{language}
# Complete working example
```

## Error Handling

{Common errors and how to handle them}

### {Error Type}

**Cause**: {Why this happens}
**Solution**: {How to fix it}

## Best Practices

- {Best practice 1}
- {Best practice 2}

## Troubleshooting

### {Problem}

**Symptom**: {What user sees}
**Cause**: {Why it happens}
**Fix**: {How to resolve}

## Migration Guide

{If there are breaking changes}

### Upgrading from {version}

**Changes**:
- {Change 1}
- {Change 2}

**Migration Steps**:
1. {Step 1}
2. {Step 2}

**Code Changes**:
```{language}
# Before
old_code()

# After
new_code()
```

## FAQ

**Q: {Question}**
A: {Answer}

## Related

- [Related Feature 1](link)
- [Related Feature 2](link)

## See Also

- {External resource or documentation}
```

### 6. Update API Documentation

Create or update API reference documentation:

**For Python**:
- Ensure docstrings are comprehensive
- Use sphinx-compatible format
- Document all parameters and return values
- Include usage examples in docstrings

**For JavaScript/TypeScript**:
- Add JSDoc comments
- Document types explicitly
- Include example usage
- Generate API docs with tool (if configured)

**For REST APIs**:
- Document all endpoints
- Include request/response examples
- Note authentication requirements
- List possible error codes

### 7. Add Usage Examples

Create practical, working examples:

**Characteristics of good examples**:
- Complete and runnable
- Demonstrate common use cases
- Start simple, build to complex
- Include error handling
- Show best practices
- Comment key parts

**Example locations**:
- In documentation files
- In `examples/` directory
- In docstrings
- In README.md

### 8. Update Changelog

Add entry to CHANGELOG.md (if it exists):

```markdown
## [Version] - YYYY-MM-DD

### Added
- {New feature description} ([#issue](link))

### Changed
- {Changed behavior} ([#issue](link))

### Fixed
- {Bug fix} ([#issue](link))

### Deprecated
- {Deprecated feature} ([#issue](link))
```

Follow [Keep a Changelog](https://keepachangelog.com/) format.

### 9. Create Migration Guides

If there are breaking changes:

**Migration guide should include**:
- What changed and why
- Impact on existing code
- Step-by-step migration process
- Code examples (before/after)
- Timeline for deprecations
- Support resources

### 10. Update Configuration Documentation

Document new configuration options:

**Include**:
- Configuration file examples
- Environment variables
- Default values
- Valid value ranges
- Examples for common scenarios

### 11. Verify Documentation Quality

**Check for**:
- Spelling and grammar
- Broken links
- Incorrect code examples
- Missing sections
- Consistency with implementation
- Clear writing

**Test all examples**:
- Run code examples to verify they work
- Check commands execute successfully
- Validate configuration examples
- Ensure links resolve correctly

### 12. Output Summary

Report:
- Documentation files created/updated
- Sections added to README
- Examples created
- API documentation coverage
- Migration guides created (if any)
- Next steps (should be task completion)

## Example Usage

```
/document specs/user-authentication.md

Generates documentation for the authentication feature.
```

```
/document User profile editing

Searches for matching spec and creates documentation.
```

```
/document

Documents the most recently reviewed feature.
```

## Response Format

```
Documentation complete: {feature name}

Documentation Created/Updated:
- docs/{feature-name}.md - Complete feature documentation
- README.md - Added {feature} section
- examples/{feature-example}.{ext} - Working example

Documentation Highlights:
- API reference for {N} functions/classes
- {N} usage examples added
- Configuration guide with {N} options
- Migration guide from v{old} to v{new} (if applicable)

All examples tested and verified working.

Next: Task complete - ready for release/merge
```

## Notes

- **Model**: Use Sonnet for documentation (Opus not needed for writing docs)
- **Clarity**: Write for the target audience (users, not developers)
- **Examples**: Always include working code examples
- **Accuracy**: Ensure documentation matches implementation
- **Completeness**: Cover all user-facing functionality
- **Consistency**: Follow project documentation style
- **Testing**: Verify all examples actually work
- **Maintenance**: Document configuration and troubleshooting

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Write implementation details users don't need
  **Do**: Focus on how to use the feature

- **Don't**: Skip examples
  **Do**: Provide clear, working code examples

- **Don't**: Use jargon without explanation
  **Do**: Write clearly for the target audience

- **Don't**: Document code that doesn't exist
  **Do**: Verify documentation matches implementation

- **Don't**: Create documentation that's hard to find
  **Do**: Link from README and organize logically

- **Don't**: Forget to update existing docs
  **Do**: Check for documentation that needs updates

- **Don't**: Write vague or unclear instructions
  **Do**: Provide specific, actionable guidance

- **Don't**: Skip error handling documentation
  **Do**: Document common errors and solutions

## Documentation Types

### User Documentation

Focus: How to use the feature
- Getting started guides
- Tutorials
- Usage examples
- Configuration guides
- Troubleshooting

### API Documentation

Focus: Function/class interfaces
- Function signatures
- Parameter descriptions
- Return values
- Exceptions
- Usage examples

### Developer Documentation

Focus: How to extend/contribute
- Architecture overview
- Code organization
- Development setup
- Contributing guidelines
- Testing approach

### Reference Documentation

Focus: Complete details
- Full API reference
- Configuration options
- Environment variables
- Command-line flags
- All available features

## Writing Guidelines

### Clarity

- Use simple, direct language
- Define technical terms
- Break complex topics into steps
- Use active voice
- Keep sentences concise

### Structure

- Start with overview
- Progress from simple to complex
- Group related information
- Use headings effectively
- Include table of contents for long docs

### Code Examples

- Keep examples focused
- Start with simplest case
- Build complexity gradually
- Include comments
- Show complete, runnable code
- Test all examples

### Formatting

- Use consistent markdown style
- Code blocks with language tags
- Tables for structured data
- Lists for sequential items
- Bold for emphasis
- Links for references

## Integration

This command is phase 5 of workflows:
- **SDLC workflow**: /plan → /implement → /test → /review → **/document** → update

The reviewed implementation from `/review` is input for this command.
The documented feature is ready for release/merge after this phase.

## Success Criteria

Documentation phase is complete when:
- [ ] README.md updated (if needed)
- [ ] Feature documentation created
- [ ] API documentation complete
- [ ] Usage examples provided and tested
- [ ] Configuration documented
- [ ] Migration guide created (if breaking changes)
- [ ] Changelog updated
- [ ] All examples verified working
- [ ] Links are valid
- [ ] Documentation summary provided

## Documentation Checklist

### Overview Documentation
- [ ] Feature purpose explained
- [ ] Use cases described
- [ ] Benefits outlined
- [ ] Prerequisites listed

### Installation/Setup
- [ ] Installation steps provided
- [ ] Dependencies documented
- [ ] Configuration explained
- [ ] Environment setup covered

### Usage Documentation
- [ ] Basic usage examples
- [ ] Advanced usage patterns
- [ ] Common scenarios covered
- [ ] Best practices shared

### API Documentation
- [ ] All public functions documented
- [ ] Parameters described
- [ ] Return values explained
- [ ] Exceptions listed
- [ ] Examples included

### Examples
- [ ] Simple example provided
- [ ] Complex example included
- [ ] Edge cases demonstrated
- [ ] All examples tested

### Reference
- [ ] Configuration options listed
- [ ] Environment variables documented
- [ ] Command-line flags explained
- [ ] All features covered

### Maintenance
- [ ] Troubleshooting guide
- [ ] Common errors documented
- [ ] FAQ section (if needed)
- [ ] Migration guide (if applicable)

## Framework-Specific Notes

### Python Projects

**Docstring format**:
```python
def function(param1: str, param2: int = 0) -> bool:
    """Brief description of function.

    Longer description explaining what the function does,
    when to use it, and important details.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter (default: 0)

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: If param1 is empty
        TypeError: If param2 is not an integer

    Example:
        >>> function("test", 5)
        True
    """
```

**Tools**: Sphinx, MkDocs, pdoc

### JavaScript/TypeScript Projects

**JSDoc format**:
```javascript
/**
 * Brief description of function.
 *
 * Longer description explaining functionality.
 *
 * @param {string} param1 - Description of first parameter
 * @param {number} [param2=0] - Description of optional parameter
 * @returns {boolean} True if successful, false otherwise
 * @throws {Error} If param1 is empty
 *
 * @example
 * function("test", 5)
 * // returns true
 */
```

**Tools**: JSDoc, TypeDoc, documentation.js

### REST API Projects

**Endpoint documentation**:
```markdown
### GET /api/resource

Retrieve a resource by ID.

**Authentication**: Required (Bearer token)

**Parameters**:
- `id` (path, required): Resource ID

**Query Parameters**:
- `include` (string, optional): Related resources to include

**Request Example**:
```http
GET /api/resource/123?include=author
Authorization: Bearer {token}
```

**Response Example** (200 OK):
```json
{
  "id": "123",
  "name": "Example",
  "author": {
    "id": "456",
    "name": "John Doe"
  }
}
```

**Error Responses**:
- `404 Not Found`: Resource does not exist
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
```

**Tools**: OpenAPI/Swagger, Postman, API Blueprint

### CLI Tool Projects

**Command documentation**:
```markdown
### command-name

Brief description of what the command does.

**Usage**:
```bash
command-name [options] <arg1> [arg2]
```

**Arguments**:
- `arg1` - Description of required argument
- `arg2` - Description of optional argument

**Options**:
- `-f, --flag`: Description of flag
- `-o, --option <value>`: Description of option with value

**Examples**:
```bash
# Basic usage
command-name input.txt

# With options
command-name -f --option=value input.txt output.txt
```

**Exit Codes**:
- `0`: Success
- `1`: General error
- `2`: Invalid arguments
```

## Common Documentation Sections

### For Libraries

- Overview and purpose
- Installation instructions
- Quick start guide
- API reference
- Usage examples
- Configuration
- Best practices
- Migration guides
- Contributing guidelines

### For Applications

- Overview and features
- Installation/setup
- User guide
- Configuration
- Troubleshooting
- FAQ
- Changelog
- License

### For APIs

- Authentication
- Endpoint reference
- Request/response formats
- Error codes
- Rate limiting
- Versioning
- Examples
- SDKs/clients

### For CLI Tools

- Installation
- Command reference
- Usage examples
- Configuration
- Exit codes
- Troubleshooting
- Man pages (Unix)

## Accessibility Considerations

Make documentation accessible:
- Use descriptive link text (not "click here")
- Provide alt text for images/diagrams
- Use semantic headings (h1, h2, h3)
- Ensure sufficient contrast
- Support screen readers
- Test with accessibility tools

## Version-Specific Documentation

When documenting different versions:
- Clearly label version requirements
- Use version badges
- Maintain docs for supported versions
- Archive old version docs
- Provide version switcher (if docs site)
- Note version-specific features

## Documentation Maintenance

Keep documentation current:
- Update with code changes
- Review during releases
- Fix reported issues
- Update examples
- Refresh screenshots
- Validate links
- Archive outdated content
