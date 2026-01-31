# /prime_feature - Prime context for feature work

Load context specific to implementing a feature.

## Input

$ARGUMENTS - Feature name or description

## Process

1. **Run base prime**
   - Execute /prime workflow

2. **Feature-specific context**
   - Search for related files: `git grep -l "$ARGUMENTS"`
   - Read spec if exists: `specs/*$ARGUMENTS*.md`
   - Find related tests

3. **Dependencies**
   - Identify imports/dependencies in related files
   - Note patterns used

4. **Report**
   - List relevant files found
   - Summarize patterns to follow
   - Note any existing related code

## Output

Context primed for feature: $ARGUMENTS
