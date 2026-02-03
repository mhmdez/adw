# /plan_fastapi - FastAPI Application Planner

Generate a comprehensive implementation plan for FastAPI applications with API-first design.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
description: Plan FastAPI applications with API-first design
model: opus
```

## Purpose

Create detailed technical plans for FastAPI applications. This planner understands FastAPI-specific patterns including router organization, Pydantic models, dependency injection, database integration, and OpenAPI schema generation.

## When to Use

- Building REST APIs with FastAPI
- Creating backend services with Python
- Designing API-first applications
- Planning microservices architecture
- Integrating with databases (SQLAlchemy, Supabase, MongoDB)

## Input

$ARGUMENTS - Feature description or API requirements

Examples:
```
/plan_fastapi Add user authentication with JWT
/plan_fastapi Create CRUD endpoints for products
/plan_fastapi Implement file upload service
```

## FastAPI-Specific Knowledge

### Router Patterns

Organize routers by resource/domain:

```
src/
├── main.py                 # FastAPI app entry point
├── routers/
│   ├── __init__.py
│   ├── auth.py            # /auth endpoints
│   ├── users.py           # /users endpoints
│   └── products.py        # /products endpoints
├── models/                # Pydantic models
│   ├── __init__.py
│   ├── user.py
│   └── product.py
├── schemas/               # Database schemas (SQLAlchemy)
│   ├── __init__.py
│   └── base.py
├── services/              # Business logic
│   ├── __init__.py
│   └── auth_service.py
├── dependencies/          # Dependency injection
│   ├── __init__.py
│   ├── database.py
│   └── auth.py
└── core/
    ├── config.py          # Settings
    └── security.py        # Security utilities
```

### Pydantic Models

Define request/response schemas with Pydantic:

```python
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Request model
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)

# Response model
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Database model (SQLAlchemy)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Dependency Injection

Use FastAPI's dependency system:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    user = verify_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# Usage in endpoint
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### Error Handling

Structured error responses:

```python
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )

class APIError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message}
        )

# Usage
raise APIError("USER_NOT_FOUND", "User does not exist", 404)
```

### Background Tasks

For async operations:

```python
from fastapi import BackgroundTasks

async def send_email(email: str, message: str):
    # Email sending logic
    pass

@router.post("/register")
async def register(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    new_user = create_user(db, user)
    background_tasks.add_task(send_email, user.email, "Welcome!")
    return new_user
```

### Middleware

Request/response processing:

```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        response.headers["X-Process-Time"] = str(duration)
        return response
```

### OpenAPI Schema

FastAPI auto-generates OpenAPI (Swagger) docs:

```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="API for managing resources",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
    openapi_url="/openapi.json"
)

# Tag organization
@router.get("/users", tags=["users"], summary="List users")
async def list_users():
    """
    Retrieve a list of all users.

    - **skip**: Number of records to skip
    - **limit**: Max records to return
    """
    pass
```

## Planning Process

### 1. Understand API Requirements

- Identify resources and their relationships
- Define CRUD operations needed
- Determine authentication requirements
- Note rate limiting needs
- Identify background processing needs

### 2. Design API Schema

Create OpenAPI-first design:

```yaml
openapi: 3.0.0
info:
  title: Feature API
  version: 1.0.0

paths:
  /resource:
    get:
      summary: List resources
      responses:
        200:
          description: Success
    post:
      summary: Create resource
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResourceCreate'
      responses:
        201:
          description: Created

components:
  schemas:
    ResourceCreate:
      type: object
      required: [name]
      properties:
        name:
          type: string
```

### 3. Plan File Structure

Define modules and their responsibilities:

- **routers/**: API endpoint definitions
- **models/**: Pydantic request/response schemas
- **schemas/**: Database models (SQLAlchemy/Tortoise)
- **services/**: Business logic layer
- **dependencies/**: Reusable dependencies
- **core/**: Configuration, security, utilities

### 4. Implementation Steps

Typical order:
1. Define Pydantic models (request/response)
2. Create database schemas (if needed)
3. Implement service layer (business logic)
4. Create router with endpoints
5. Add dependencies (auth, db session)
6. Register router in main.py
7. Write tests

### 5. Testing Strategy

```python
from fastapi.testclient import TestClient
import pytest

@pytest.fixture
def client():
    return TestClient(app)

def test_create_user(client):
    response = client.post("/users", json={
        "email": "test@example.com",
        "password": "password123",
        "name": "Test User"
    })
    assert response.status_code == 201
    assert "id" in response.json()

# Async testing
import pytest_asyncio
from httpx import AsyncClient

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_async_endpoint(async_client):
    response = await async_client.get("/async-endpoint")
    assert response.status_code == 200
```

## Output Spec Format

Create spec at `specs/{feature-slug}.md`:

```markdown
# {Feature Name} - FastAPI Implementation

## Overview

{Brief description of the API feature}

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /resource | List resources |
| POST | /resource | Create resource |
| GET | /resource/{id} | Get resource by ID |
| PUT | /resource/{id} | Update resource |
| DELETE | /resource/{id} | Delete resource |

## Data Models

### Request Models

```python
class ResourceCreate(BaseModel):
    name: str
    description: str | None = None
```

### Response Models

```python
class ResourceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
```

## File Structure

- `src/routers/resource.py` - Resource endpoints
- `src/models/resource.py` - Pydantic models
- `src/schemas/resource.py` - Database schema
- `src/services/resource_service.py` - Business logic
- `tests/test_resource.py` - API tests

## Implementation Steps

1. **Create Pydantic models** (models/resource.py)
   - ResourceCreate for input
   - ResourceResponse for output
   - ResourceUpdate for PATCH

2. **Create database schema** (schemas/resource.py)
   - SQLAlchemy model with columns
   - Indexes and constraints

3. **Implement service layer** (services/resource_service.py)
   - create_resource()
   - get_resource()
   - list_resources()
   - update_resource()
   - delete_resource()

4. **Create router** (routers/resource.py)
   - GET /resource - list
   - POST /resource - create
   - GET /resource/{id} - read
   - PUT /resource/{id} - update
   - DELETE /resource/{id} - delete

5. **Add tests** (tests/test_resource.py)
   - Test each endpoint
   - Test validation errors
   - Test auth requirements

## Dependencies

- fastapi
- pydantic
- sqlalchemy (if using SQL)
- python-jose (if JWT auth)
- passlib (if password hashing)

## Testing Plan

### Unit Tests
- Model validation
- Service functions

### Integration Tests
- Endpoint responses
- Database operations
- Authentication flow

### Edge Cases
- Invalid input
- Not found errors
- Duplicate entries
- Auth failures
```

## Response Format

```
FastAPI Plan: {feature_name}

Spec created: specs/{feature-slug}.md

API Design:
- {N} endpoints defined
- {M} Pydantic models
- {K} database tables

Key Decisions:
- Router: /api/v1/{resource}
- Auth: JWT Bearer tokens
- Database: PostgreSQL + SQLAlchemy

File Structure:
- routers/{resource}.py
- models/{resource}.py
- services/{resource}_service.py
- tests/test_{resource}.py

Implementation: {N} steps defined

Next: Run `/implement specs/{feature-slug}.md`
```

## Anti-Patterns

Avoid these FastAPI mistakes:

- **Don't**: Put business logic in routers
  **Do**: Use a service layer for business logic

- **Don't**: Return raw database models
  **Do**: Use Pydantic response models

- **Don't**: Hardcode configuration
  **Do**: Use pydantic-settings for config

- **Don't**: Skip input validation
  **Do**: Define strict Pydantic models

- **Don't**: Ignore async properly
  **Do**: Use async/await consistently

- **Don't**: Create one giant router
  **Do**: Split by resource/domain

## Best Practices

- Use dependency injection for database sessions
- Define response_model for automatic serialization
- Use status codes from `fastapi.status`
- Group endpoints with tags for docs
- Add docstrings for OpenAPI descriptions
- Use Path/Query/Body for parameter validation
- Implement proper CORS for frontend access
- Use background tasks for slow operations
- Version your API (/api/v1/)
