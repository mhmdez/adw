# Spec: Specialized Planners

## Job to Be Done
Create per-stack planning commands that leverage framework-specific knowledge.

## Acceptance Criteria

### 1. FastAPI Planner
- [ ] Create `.claude/commands/plan_fastapi.md`
- [ ] Knows:
  - FastAPI router patterns
  - Pydantic models
  - Dependency injection
  - OpenAPI schema
- [ ] Generates API-first plans

### 2. React Planner
- [ ] Create `.claude/commands/plan_react.md`
- [ ] Knows:
  - Component hierarchy
  - State management (useState, useReducer, Zustand)
  - Hooks patterns
  - Testing with React Testing Library
- [ ] Generates component-first plans

### 3. Next.js Planner
- [ ] Create `.claude/commands/plan_nextjs.md`
- [ ] Knows:
  - App Router vs Pages Router
  - Server Components
  - API routes
  - Middleware
- [ ] Considers SSR/SSG implications

### 4. Supabase Planner
- [ ] Create `.claude/commands/plan_supabase.md`
- [ ] Knows:
  - PostgreSQL schema design
  - Row Level Security
  - Edge Functions
  - Realtime subscriptions
- [ ] Plans database-first

### 5. Auto-Detect Planner
- [ ] `adw plan` auto-selects planner based on:
  - `requirements.txt` → Python stack
  - `package.json` → Node stack
  - Framework-specific files
- [ ] Falls back to generic planner

## Technical Notes
- Planners are prompts, not code
- Each planner ~500 tokens of specialized context
- Can combine multiple planners for full-stack

## Testing
- [ ] Test auto-detection
- [ ] Verify each planner produces framework-appropriate plans
