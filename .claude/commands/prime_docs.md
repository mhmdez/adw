# /prime_docs - Prime context for documentation

Load context specific to writing and updating documentation.

## Metadata

```yaml
allowed-tools: [Read, Bash, Glob, Grep]
description: Prime context for documentation
```

## Input

$ARGUMENTS - Feature or topic to document (optional)

## Purpose

Quickly load documentation-relevant context for creating or updating docs. Focuses on documentation locations, style guidelines, and existing examples to maintain consistency.

## When to Use

- Writing new documentation
- Updating existing docs
- Creating API documentation
- Writing README files
- Documenting architecture decisions

## Process

### 1. Documentation Locations

Find where documentation lives:

```bash
# Find doc directories
git ls-files | grep -E "^docs/|^doc/|README|CONTRIBUTING|ARCHITECTURE" | head -15

# Find inline documentation
git ls-files | grep -E "\.md$|\.rst$|\.adoc$" | head -20
```

Map:
- Main docs directory (`docs/`, `doc/`, `documentation/`)
- README locations (root and subdirectories)
- Architecture/design docs
- API documentation

### 2. Documentation Style

Identify style and format:

```bash
# Check for style guide
git ls-files | grep -iE "style|guide|contributing" | head -5

# Look at existing docs structure
head -50 docs/*.md 2>/dev/null || head -50 README.md
```

Note:
- Format (Markdown, RST, AsciiDoc)
- Heading conventions
- Code block style
- Link patterns (relative vs absolute)

### 3. Documentation Generators

Check for doc generation tools:

```bash
# Look for doc tools config
git ls-files | grep -E "mkdocs|sphinx|docusaurus|vuepress|docfx|typedoc|jsdoc" | head -5

# API doc configuration
git ls-files | grep -E "openapi|swagger|\.api\." | head -3
```

Identify:
- Static site generator (MkDocs, Sphinx, Docusaurus)
- API doc tools (OpenAPI, Swagger, TypeDoc)
- Build/deploy process

### 4. Example Documentation

Read example docs to understand patterns:

```bash
# Sample documentation files
git ls-files | grep -E "\.md$" | head -3
```

Read 1-2 existing docs to understand:
- Section structure
- Code example format
- Callout/admonition style
- Cross-reference conventions

### 5. README Conventions

Check README patterns:

```bash
# Find all READMEs
git ls-files | grep -i readme | head -10

# Check main README structure
head -100 README.md 2>/dev/null
```

Note sections:
- Installation
- Usage
- Contributing
- License

### 6. Topic-Specific Docs

If `$ARGUMENTS` is provided, find related docs:

```bash
# Existing documentation
git ls-files | grep -E "\.md$|\.rst$" | xargs grep -li "$ARGUMENTS" 2>/dev/null | head -5

# Source code comments
git grep -n "@doc\|@param\|@returns\|:param\|:returns\|\"\"\"" | grep -i "$ARGUMENTS" | head -5
```

### 7. Report Summary

Provide a summary including:

- **Locations**: Where docs live
- **Format**: Documentation format and style
- **Tools**: Doc generators and build process
- **Patterns**: Structure and conventions
- **Related Docs**: Existing docs for `$ARGUMENTS`

## Output Format

```
Documentation Context
====================

Locations:
- Main docs: {docs directory}
- README: {root and subdirectory READMEs}
- API docs: {OpenAPI, generated docs location}
- Architecture: {ADR location if exists}

Format:
- Type: {Markdown, RST, AsciiDoc}
- Headings: {# style, = underline, etc.}
- Code blocks: {fenced, indented}
- Links: {relative to docs root}

Tools:
- Generator: {MkDocs, Sphinx, Docusaurus, none}
- Build: {build command}
- Deploy: {deployment process}

Style:
- Sections: {standard sections used}
- Tone: {technical, casual, formal}
- Examples: {how code examples are formatted}

Related Docs (for "$ARGUMENTS"):
- {doc_file.md - description}

Context primed for documentation.
```

## Example Usage

```
/prime_docs "authentication API"

Loads doc context and finds auth-related documentation.
```

```
/prime_docs

Loads general documentation context.
```

## Notes

- **Consistent**: Helps maintain documentation consistency
- **Discoverable**: Maps existing documentation structure
- **Tool-aware**: Identifies documentation toolchain
- **Example-driven**: Shows patterns from existing docs

## Documentation Best Practices

### Markdown Structure
```markdown
# Title (H1 - one per file)

Brief description.

## Section (H2)

Content with **bold** and `code`.

### Subsection (H3)

More details.

## Code Examples

\`\`\`python
def example():
    return "documented"
\`\`\`

## See Also

- [Related Doc](./related.md)
```

### API Documentation
```markdown
## `function_name(param1, param2)`

Brief description.

### Parameters

| Name | Type | Description |
|------|------|-------------|
| param1 | string | Description |
| param2 | int | Description |

### Returns

Description of return value.

### Example

\`\`\`python
result = function_name("value", 42)
\`\`\`
```

### Architecture Decision Records (ADR)
```markdown
# ADR-001: Title

## Status
Accepted

## Context
Why we needed to make this decision.

## Decision
What we decided.

## Consequences
What happens as a result.
```

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Write docs that duplicate code comments
  **Do**: Focus on why and how, not just what

- **Don't**: Create orphaned docs with no links
  **Do**: Cross-reference related documentation

- **Don't**: Ignore existing style conventions
  **Do**: Match the tone and format of existing docs

- **Don't**: Write docs without code examples
  **Do**: Include runnable examples where possible

## Integration

This command works well with:
- `/prime` - General codebase orientation
- `/prime_feature` - Feature context for feature docs
- `/document` - Generate documentation automatically
