# Spec: Agent Experts

## Job to Be Done
Create domain-specific expert agents that specialize in particular areas and improve over time.

## Acceptance Criteria

### 1. Expert Framework
- [ ] Create `src/adw/experts/base.py`
- [ ] Base class `Expert`:
  - `domain: str` — Area of expertise
  - `knowledge: dict` — Accumulated knowledge
  - `plan(task)` — Create specialized plan
  - `build(spec)` — Implement with expertise
  - `improve(feedback)` — Learn from outcomes

### 2. Frontend Expert
- [ ] Create `src/adw/experts/frontend.py`
- [ ] Specializes in: React, Vue, CSS, accessibility
- [ ] Knows:
  - Component patterns
  - State management
  - Styling conventions
  - Browser compatibility

### 3. Backend Expert
- [ ] Create `src/adw/experts/backend.py`
- [ ] Specializes in: FastAPI, Supabase, REST APIs
- [ ] Knows:
  - API design patterns
  - Database queries
  - Authentication flows
  - Error handling

### 4. AI Expert
- [ ] Create `src/adw/experts/ai.py`
- [ ] Specializes in: LLM integration, prompts, agents
- [ ] Knows:
  - Prompt engineering patterns
  - Token optimization
  - Model selection
  - Evaluation techniques

### 5. Expert Selection
- [ ] Auto-detect which expert to use based on task
- [ ] Keywords: "frontend", "UI", "CSS" → Frontend Expert
- [ ] File patterns: `*.tsx`, `*.vue` → Frontend Expert
- [ ] Multiple experts can collaborate on complex tasks

## Technical Notes
- Experts are just specialized prompts + context
- Knowledge stored in `~/.adw/experts/<name>/knowledge.json`
- Self-improvement updates knowledge after each task

## Testing
- [ ] Test expert selection logic
- [ ] Test knowledge persistence
- [ ] Verify expertise improves output quality
