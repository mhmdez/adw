"""Backend expert for FastAPI, Supabase, and REST APIs.

Specializes in:
- FastAPI patterns (routers, dependencies, Pydantic)
- Supabase integration (PostgreSQL, RLS, Edge Functions)
- REST API design (endpoints, authentication, validation)
- Database operations (queries, migrations, transactions)
"""

from __future__ import annotations

from typing import Any

from .base import Expert, register_expert


@register_expert
class BackendExpert(Expert):
    """Expert in backend development."""

    domain = "backend"
    specializations = [
        "FastAPI",
        "Supabase",
        "PostgreSQL",
        "REST APIs",
        "authentication",
        "database design",
        "Python",
    ]
    description = "Backend development expert for FastAPI, Supabase, and REST APIs"

    # Default best practices for backend
    DEFAULT_BEST_PRACTICES = [
        "Use Pydantic models for request/response validation",
        "Implement proper error handling with HTTPException",
        "Use dependency injection for shared resources",
        "Apply Row Level Security (RLS) for data access control",
        "Use async/await for I/O-bound operations",
        "Implement proper logging for debugging and monitoring",
        "Use transactions for multi-step database operations",
        "Validate all user inputs at API boundaries",
    ]

    # Default patterns
    DEFAULT_PATTERNS = [
        "Repository pattern for database access",
        "Service layer for business logic",
        "Dependency injection for database sessions",
        "Background tasks for long-running operations",
        "Middleware for cross-cutting concerns",
        "API versioning with router prefixes",
        "Pagination for list endpoints",
    ]

    def plan(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Create a backend-focused implementation plan.

        Args:
            task: Task description.
            context: Additional context (files, framework, etc.)

        Returns:
            Markdown-formatted backend plan.
        """
        ctx = context or {}
        framework = ctx.get("framework", "FastAPI")
        database = ctx.get("database", "PostgreSQL")

        # Detect specifics from task
        task_lower = task.lower()
        if "supabase" in task_lower:
            database = "Supabase"
        if "django" in task_lower:
            framework = "Django"
        if "flask" in task_lower:
            framework = "Flask"

        plan_content = f"""## Backend Implementation Plan

### Task
{task}

### Stack
- **Framework:** {framework}
- **Database:** {database}

### API Design

1. **Endpoint Analysis**
   - Identify required endpoints
   - Define HTTP methods (GET, POST, PUT, DELETE)
   - Plan URL structure
   - Define request/response schemas

2. **Data Model**
   - Design database schema
   - Define relationships
   - Plan indexes for query optimization
   - Consider data validation rules

3. **Authentication & Authorization**
   - Identify protected endpoints
   - Plan auth flow (JWT, session, OAuth)
   - Define permission levels
   - Implement RLS if using Supabase

4. **Error Handling**
   - Define error response format
   - Handle validation errors
   - Handle business logic errors
   - Log errors appropriately

5. **Testing Strategy**
   - Unit tests for services
   - Integration tests for endpoints
   - Mock external dependencies

{self._get_framework_specific_guidance(framework)}

### Expertise Applied

{self.get_context()}
"""
        return plan_content

    def _get_framework_specific_guidance(self, framework: str) -> str:
        """Get framework-specific implementation guidance."""
        if framework.lower() == "fastapi":
            return """### FastAPI-Specific Guidance

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["resource"])

class ResourceCreate(BaseModel):
    name: str
    description: str | None = None

class ResourceResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

@router.post("/resources", response_model=ResourceResponse)
async def create_resource(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate and create
    resource = await service.create(db, data, user.id)
    return resource

@router.get("/resources/{id}", response_model=ResourceResponse)
async def get_resource(id: int, db: Session = Depends(get_db)):
    resource = await service.get(db, id)
    if not resource:
        raise HTTPException(status_code=404, detail="Not found")
    return resource
```

- Use path operation decorators
- Define Pydantic schemas for validation
- Use dependency injection
- Return proper status codes
"""
        elif framework.lower() == "django":
            return """### Django-Specific Guidance

```python
from django.db import models
from rest_framework import viewsets, serializers

class Resource(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ['id', 'name', 'created_at']

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
```

- Use Django REST Framework for APIs
- Define models in models.py
- Use serializers for validation
- ViewSets for CRUD operations
"""
        else:  # Flask
            return """### Flask-Specific Guidance

```python
from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields

bp = Blueprint('resources', __name__, url_prefix='/api/v1')

class ResourceSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)

@bp.route('/resources', methods=['POST'])
def create_resource():
    schema = ResourceSchema()
    data = schema.load(request.json)
    resource = service.create(data)
    return jsonify(schema.dump(resource)), 201

@bp.route('/resources/<int:id>')
def get_resource(id):
    resource = service.get(id)
    if not resource:
        return jsonify({"error": "Not found"}), 404
    return jsonify(ResourceSchema().dump(resource))
```

- Use Blueprints for organization
- Marshmallow for serialization
- Application factory pattern
"""

    def get_context(self) -> str:
        """Get backend expertise context for prompts."""
        # Combine default and learned knowledge
        patterns = self.DEFAULT_PATTERNS.copy()
        patterns.extend(self.knowledge.patterns)

        practices = self.DEFAULT_BEST_PRACTICES.copy()
        practices.extend(self.knowledge.best_practices)

        # Deduplicate
        patterns = list(dict.fromkeys(patterns))
        practices = list(dict.fromkeys(practices))

        context = f"""## Backend Expertise

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
        """Generate backend implementation guidance.

        Args:
            spec: Implementation specification.
            context: Additional context.

        Returns:
            Backend-specific implementation guidance.
        """
        return f"""## Backend Implementation Guidance

### Specification
{spec}

### Implementation Checklist

- [ ] Define Pydantic models for request/response
- [ ] Create database model/table
- [ ] Implement service layer logic
- [ ] Create API endpoint(s)
- [ ] Add authentication/authorization
- [ ] Handle errors gracefully
- [ ] Add logging
- [ ] Write tests

### API Response Format

```json
{{
  "data": {{ ... }},
  "meta": {{
    "page": 1,
    "per_page": 20,
    "total": 100
  }}
}}
```

### Error Response Format

```json
{{
  "error": {{
    "code": "VALIDATION_ERROR",
    "message": "Human readable message",
    "details": [
      {{ "field": "name", "message": "Required field" }}
    ]
  }}
}}
```

### Testing Template

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_resource():
    response = client.post("/api/v1/resources", json={{
        "name": "Test Resource"
    }})
    assert response.status_code == 201
    assert response.json()["name"] == "Test Resource"

def test_get_resource_not_found():
    response = client.get("/api/v1/resources/999")
    assert response.status_code == 404
```

{self.get_context()}
"""
