"""Frontend expert for React, Vue, CSS, and accessibility.

Specializes in:
- React patterns (hooks, components, state management)
- Vue.js patterns (Composition API, Pinia, Vue Router)
- CSS and styling (Tailwind, CSS-in-JS, responsive design)
- Accessibility (ARIA, keyboard navigation, screen readers)
"""

from __future__ import annotations

from typing import Any

from .base import Expert, register_expert


@register_expert
class FrontendExpert(Expert):
    """Expert in frontend development."""

    domain = "frontend"
    specializations = [
        "React",
        "Vue.js",
        "CSS",
        "Tailwind CSS",
        "TypeScript",
        "accessibility",
        "responsive design",
    ]
    description = "Frontend development expert for React, Vue, CSS, and accessibility"

    # Default best practices for frontend
    DEFAULT_BEST_PRACTICES = [
        "Use semantic HTML elements for better accessibility",
        "Implement proper keyboard navigation for interactive elements",
        "Use lazy loading for images and large components",
        "Memoize expensive calculations and components",
        "Keep components small and focused on single responsibility",
        "Use CSS custom properties for theming",
        "Test components with React Testing Library or Vue Test Utils",
        "Use error boundaries for graceful error handling",
    ]

    # Default patterns
    DEFAULT_PATTERNS = [
        "Container/Presentational component pattern",
        "Custom hooks for shared logic (React)",
        "Composables for shared logic (Vue)",
        "Render props for flexible components",
        "Compound components for related UI elements",
        "Controlled vs uncontrolled form inputs",
        "Optimistic UI updates for better UX",
    ]

    def plan(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Create a frontend-focused implementation plan.

        Args:
            task: Task description.
            context: Additional context (files, framework, etc.)

        Returns:
            Markdown-formatted frontend plan.
        """
        ctx = context or {}
        framework = ctx.get("framework", "React")

        # Detect framework from task/context
        task_lower = task.lower()
        if "vue" in task_lower:
            framework = "Vue"
        elif "react" in task_lower:
            framework = "React"

        plan_content = f"""## Frontend Implementation Plan

### Task
{task}

### Framework
{framework}

### Component Structure

1. **Analysis**
   - Identify UI components needed
   - Determine component hierarchy
   - Plan state management approach
   - Identify reusable patterns

2. **Component Breakdown**
   - Create component tree diagram
   - Define props interfaces
   - Plan component composition

3. **State Management**
   - Identify local vs shared state
   - Choose state management approach
   - Plan data flow

4. **Styling Approach**
   - Use consistent styling method
   - Implement responsive design
   - Support dark/light themes if needed

5. **Accessibility Checklist**
   - [ ] Semantic HTML elements
   - [ ] ARIA labels for interactive elements
   - [ ] Keyboard navigation support
   - [ ] Focus management
   - [ ] Color contrast compliance
   - [ ] Screen reader testing

6. **Testing Strategy**
   - Unit tests for logic
   - Component tests for UI
   - Integration tests for user flows

{self._get_framework_specific_guidance(framework)}

### Expertise Applied

{self.get_context()}
"""
        return plan_content

    def _get_framework_specific_guidance(self, framework: str) -> str:
        """Get framework-specific implementation guidance."""
        if framework.lower() == "vue":
            return """### Vue-Specific Guidance

```vue
<script setup lang="ts">
// Use Composition API
import { ref, computed, onMounted } from 'vue'

// Reactive state
const count = ref(0)

// Computed properties
const doubled = computed(() => count.value * 2)

// Lifecycle hooks
onMounted(() => {
  // Setup logic
})
</script>

<template>
  <!-- Template with proper bindings -->
</template>
```

- Use `<script setup>` for cleaner code
- Prefer Composition API over Options API
- Use Pinia for global state
- Use Vue Router for navigation
"""
        else:  # React
            return """### React-Specific Guidance

```tsx
import { useState, useCallback, useMemo } from 'react';

// Functional component with hooks
export function Component({ prop }: Props) {
  const [state, setState] = useState(initialValue);

  // Memoize callbacks
  const handleClick = useCallback(() => {
    // Handle click
  }, [dependencies]);

  // Memoize expensive calculations
  const computed = useMemo(() => {
    return expensiveCalculation(state);
  }, [state]);

  return <div>{/* JSX */}</div>;
}
```

- Use functional components with hooks
- Memoize with useMemo/useCallback appropriately
- Use React.memo for pure components
- Consider Zustand or Jotai for state management
"""

    def get_context(self) -> str:
        """Get frontend expertise context for prompts."""
        # Combine default and learned knowledge
        patterns = self.DEFAULT_PATTERNS.copy()
        patterns.extend(self.knowledge.patterns)

        practices = self.DEFAULT_BEST_PRACTICES.copy()
        practices.extend(self.knowledge.best_practices)

        # Deduplicate
        patterns = list(dict.fromkeys(patterns))
        practices = list(dict.fromkeys(practices))

        context = f"""## Frontend Expertise

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
        """Generate frontend implementation guidance.

        Args:
            spec: Implementation specification.
            context: Additional context.

        Returns:
            Frontend-specific implementation guidance.
        """
        ctx = context or {}
        framework = ctx.get("framework", "React")

        return f"""## Frontend Implementation Guidance

### Specification
{spec}

### Component Checklist

- [ ] Define TypeScript interfaces for props
- [ ] Implement component with proper hooks
- [ ] Add proper accessibility attributes
- [ ] Style with consistent approach
- [ ] Add error handling
- [ ] Write tests

### Accessibility Requirements

1. **Semantic HTML**
   - Use `<button>` for clickable actions
   - Use `<a>` for navigation
   - Use heading hierarchy properly

2. **ARIA**
   - `aria-label` for icon buttons
   - `aria-expanded` for expandable content
   - `aria-live` for dynamic updates

3. **Keyboard**
   - Tab navigation works
   - Enter/Space activates buttons
   - Escape closes modals

### Testing Template

```typescript
import {{ render, screen, fireEvent }} from '@testing-library/{
            "vue" if framework.lower() == "vue" else "react"
        }';
import {{ Component }} from './Component';

describe('Component', () => {{
  it('renders correctly', () => {{
    render(<Component />);
    expect(screen.getByRole('...')).toBeInTheDocument();
  }});

  it('handles user interaction', async () => {{
    render(<Component />);
    await fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('...')).toBeVisible();
  }});
}});
```

{self.get_context()}
"""
