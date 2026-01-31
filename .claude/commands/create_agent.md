# /create_agent - Generate a new specialized agent

Create a new sub-agent configuration based on requirements.

## Input

$ARGUMENTS - Description of what the agent should do

## Process

1. **Analyze requirements**
   - What task will this agent perform?
   - What tools does it need?
   - What model is appropriate?

2. **Research patterns**
   - Read existing agents in .claude/agents/
   - Identify similar agents for reference

3. **Generate agent spec**
   Create `.claude/agents/{name}.md`:

   ```markdown
   # {Agent Name}

   ## Metadata

   ```yaml
   allowed-tools: [{minimal tool set}]
   description: {action-oriented description}
   model: {haiku|sonnet|opus}
   ```

   ## Purpose

   {What this agent does and when to use it}

   ## Workflow

   1. {Step 1}
   2. {Step 2}
   ...

   ## Response Format

   {How the agent should format its output}
   ```

4. **Validate**
   - Ensure all required sections present
   - Tools are valid
   - Description is action-oriented

## Output

Path to created agent file.
