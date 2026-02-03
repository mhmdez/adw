"""AI expert for LLM integration, prompts, and agents.

Specializes in:
- LLM integration patterns (Claude, OpenAI, etc.)
- Prompt engineering and optimization
- Agent architectures and patterns
- Token optimization and cost management
"""

from __future__ import annotations

from typing import Any

from .base import Expert, register_expert


@register_expert
class AIExpert(Expert):
    """Expert in AI and LLM development."""

    domain = "ai"
    specializations = [
        "LLM integration",
        "prompt engineering",
        "agent architectures",
        "Claude API",
        "token optimization",
        "evaluation",
        "RAG systems",
    ]
    description = "AI development expert for LLM integration, prompts, and agents"

    # Default best practices for AI
    DEFAULT_BEST_PRACTICES = [
        "Use structured outputs (JSON mode) when parsing is needed",
        "Implement proper error handling for API failures",
        "Use streaming for long responses",
        "Cache responses when appropriate",
        "Monitor token usage and costs",
        "Use system prompts for consistent behavior",
        "Implement retry logic with exponential backoff",
        "Validate and sanitize user inputs before sending to LLM",
    ]

    # Default patterns
    DEFAULT_PATTERNS = [
        "Chain of thought prompting for complex reasoning",
        "Few-shot examples for consistent output format",
        "Tool use/function calling for structured tasks",
        "Multi-turn conversations with context management",
        "Prompt templates with variable injection",
        "Retrieval-augmented generation (RAG) for knowledge",
        "Agent loops with observation-action patterns",
    ]

    def plan(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Create an AI-focused implementation plan.

        Args:
            task: Task description.
            context: Additional context (model, use case, etc.)

        Returns:
            Markdown-formatted AI implementation plan.
        """
        ctx = context or {}
        model = ctx.get("model", "Claude")
        use_case = ctx.get("use_case", "general")

        # Detect specifics from task
        task_lower = task.lower()
        if "openai" in task_lower or "gpt" in task_lower:
            model = "OpenAI"
        elif "claude" in task_lower or "anthropic" in task_lower:
            model = "Claude"
        if "agent" in task_lower:
            use_case = "agent"
        elif "rag" in task_lower or "retrieval" in task_lower:
            use_case = "RAG"
        elif "chat" in task_lower:
            use_case = "chatbot"

        plan_content = f"""## AI Implementation Plan

### Task
{task}

### Configuration
- **Model:** {model}
- **Use Case:** {use_case}

### Implementation Steps

1. **Requirements Analysis**
   - Define expected inputs and outputs
   - Identify edge cases and error scenarios
   - Determine token budget and constraints
   - Plan evaluation criteria

2. **Prompt Design**
   - Write clear system prompt
   - Define output format (text, JSON, structured)
   - Add few-shot examples if needed
   - Include error handling instructions

3. **Integration**
   - Set up API client with proper configuration
   - Implement request/response handling
   - Add streaming support if needed
   - Handle rate limits and errors

4. **Optimization**
   - Minimize token usage
   - Cache repeated queries
   - Use appropriate model for task complexity
   - Monitor costs

5. **Evaluation**
   - Define success metrics
   - Create test cases
   - Implement automated evaluation
   - Monitor production quality

{self._get_use_case_guidance(use_case, model)}

### Expertise Applied

{self.get_context()}
"""
        return plan_content

    def _get_use_case_guidance(self, use_case: str, model: str) -> str:
        """Get use case-specific guidance."""
        if use_case == "agent":
            return """### Agent Architecture Guidance

```python
from anthropic import Anthropic

client = Anthropic()

class Agent:
    def __init__(self, system_prompt: str, tools: list):
        self.system_prompt = system_prompt
        self.tools = tools
        self.messages = []

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        while True:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=self.system_prompt,
                tools=self.tools,
                messages=self.messages,
            )

            # Check for tool use
            if response.stop_reason == "tool_use":
                tool_result = self._execute_tool(response)
                self.messages.append({"role": "assistant", "content": response.content})
                self.messages.append({"role": "user", "content": tool_result})
            else:
                # Final response
                self.messages.append({"role": "assistant", "content": response.content})
                return self._extract_text(response.content)

    def _execute_tool(self, response):
        # Execute tool and return result
        pass
```

**Key Patterns:**
- Observation-action loop
- Tool result injection
- Context window management
- Error recovery and retry
"""
        elif use_case == "RAG":
            return """### RAG System Guidance

```python
from anthropic import Anthropic
import numpy as np

client = Anthropic()

class RAGSystem:
    def __init__(self, documents: list[str]):
        self.documents = documents
        self.embeddings = self._embed_documents()

    def query(self, question: str, top_k: int = 3) -> str:
        # 1. Embed the question
        q_embedding = self._embed(question)

        # 2. Find relevant documents
        relevant_docs = self._retrieve(q_embedding, top_k)

        # 3. Generate answer with context
        context = "\\n\\n".join(relevant_docs)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f\"\"\"Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer:\"\"\"
            }],
        )
        return response.content[0].text

    def _retrieve(self, query_embedding, top_k):
        # Cosine similarity search
        pass
```

**Key Patterns:**
- Chunking strategies (semantic, fixed-size)
- Embedding model selection
- Hybrid search (semantic + keyword)
- Re-ranking for relevance
"""
        elif use_case == "chatbot":
            return """### Chatbot Guidance

```python
from anthropic import Anthropic

client = Anthropic()

SYSTEM_PROMPT = \"\"\"You are a helpful assistant for [domain].
Be concise, accurate, and friendly.
If unsure, ask clarifying questions.
Never make up information.\"\"\"

class Chatbot:
    def __init__(self):
        self.messages = []

    def chat(self, user_message: str) -> str:
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=self.messages,
        )

        assistant_message = response.content[0].text
        self.messages.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def clear_history(self):
        self.messages = []
```

**Key Patterns:**
- Conversation memory management
- System prompt design
- Graceful error handling
- Session management
"""
        else:  # general
            return """### General LLM Integration

```python
from anthropic import Anthropic

client = Anthropic()

def generate_response(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 1024,
) -> str:
    \"\"\"Generate a response from Claude.\"\"\"
    messages = [{"role": "user", "content": prompt}]

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system or "You are a helpful assistant.",
        messages=messages,
    )

    return response.content[0].text

def generate_json(
    prompt: str,
    schema: dict,
) -> dict:
    \"\"\"Generate structured JSON output.\"\"\"
    system = f\"\"\"Respond only with valid JSON matching this schema:
{json.dumps(schema, indent=2)}\"\"\"

    response = generate_response(prompt, system=system)
    return json.loads(response)
```

**Key Patterns:**
- Simple request/response
- Structured outputs
- Error handling
- Token counting
"""

    def get_context(self) -> str:
        """Get AI expertise context for prompts."""
        # Combine default and learned knowledge
        patterns = self.DEFAULT_PATTERNS.copy()
        patterns.extend(self.knowledge.patterns)

        practices = self.DEFAULT_BEST_PRACTICES.copy()
        practices.extend(self.knowledge.best_practices)

        # Deduplicate
        patterns = list(dict.fromkeys(patterns))
        practices = list(dict.fromkeys(practices))

        context = f"""## AI/LLM Expertise

**Specializations:** {", ".join(self.specializations)}

### Patterns
{chr(10).join(f"- {p}" for p in patterns[:10])}

### Best Practices
{chr(10).join(f"- {p}" for p in practices[:10])}
"""

        if self.knowledge.known_issues:
            context += "\n### Known Issues\n"
            for issue, workaround in list(self.knowledge.known_issues.items())[:5]:
                context += f"- **{issue}**: {workaround}\n"

        if self.knowledge.learnings:
            context += "\n### Recent Learnings\n"
            for learning in self.knowledge.learnings[-5:]:
                context += f"- {learning}\n"

        return context

    def build(self, spec: str, context: dict[str, Any] | None = None) -> str:
        """Generate AI implementation guidance.

        Args:
            spec: Implementation specification.
            context: Additional context.

        Returns:
            AI-specific implementation guidance.
        """
        return f"""## AI Implementation Guidance

### Specification
{spec}

### Implementation Checklist

- [ ] Define clear input/output contracts
- [ ] Write system prompt
- [ ] Implement API client with error handling
- [ ] Add streaming support (if applicable)
- [ ] Implement rate limit handling
- [ ] Add token counting and cost monitoring
- [ ] Write evaluation tests
- [ ] Add logging for debugging

### Prompt Template

```python
SYSTEM_PROMPT = \"\"\"You are [role description].

Your task is to [task description].

Rules:
- [Rule 1]
- [Rule 2]

Output format:
[Format specification]
\"\"\"

USER_PROMPT_TEMPLATE = \"\"\"
[Input context]

{{user_input}}

[Output instructions]
\"\"\"
```

### Error Handling

```python
from anthropic import (
    APIError,
    RateLimitError,
    APIConnectionError,
)
import time

def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError:
            wait = 2 ** attempt
            time.sleep(wait)
        except APIConnectionError:
            time.sleep(1)
        except APIError as e:
            if e.status_code >= 500:
                time.sleep(1)
            else:
                raise
    raise Exception("Max retries exceeded")
```

{self.get_context()}
"""
