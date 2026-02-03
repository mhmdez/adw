# /plan_react - React Application Planner

Generate a comprehensive implementation plan for React applications with component-first design.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
description: Plan React applications with component-first design
model: opus
```

## Purpose

Create detailed technical plans for React applications. This planner understands React-specific patterns including component hierarchy, hooks, state management, performance optimization, and testing with React Testing Library.

## When to Use

- Building user interfaces with React
- Creating single-page applications
- Designing component libraries
- Planning state management architecture
- Implementing complex UI interactions

## Input

$ARGUMENTS - Feature description or UI requirements

Examples:
```
/plan_react Add user dashboard with real-time updates
/plan_react Create reusable form components
/plan_react Implement shopping cart with context
```

## React-Specific Knowledge

### Component Hierarchy

Organize components by responsibility:

```
src/
├── components/           # Reusable UI components
│   ├── ui/              # Primitive components
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   └── index.ts
│   │   ├── Input/
│   │   └── Modal/
│   ├── forms/           # Form components
│   │   ├── LoginForm.tsx
│   │   └── RegisterForm.tsx
│   └── layout/          # Layout components
│       ├── Header.tsx
│       ├── Sidebar.tsx
│       └── Footer.tsx
├── features/            # Feature-based modules
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── api.ts
│   └── dashboard/
├── hooks/               # Custom hooks
│   ├── useAuth.ts
│   ├── useFetch.ts
│   └── useLocalStorage.ts
├── context/             # React Context providers
│   ├── AuthContext.tsx
│   └── ThemeContext.tsx
├── services/            # API and external services
│   ├── api.ts
│   └── auth.ts
├── types/               # TypeScript types
│   └── index.ts
└── utils/               # Utility functions
    └── helpers.ts
```

### Component Patterns

Functional components with hooks:

```tsx
// Component with TypeScript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  children,
  onClick,
}: ButtonProps) {
  return (
    <button
      className={cn('btn', `btn-${variant}`, `btn-${size}`)}
      onClick={onClick}
      disabled={loading}
    >
      {loading ? <Spinner size="sm" /> : children}
    </button>
  );
}
```

### Hooks Patterns

Custom hooks for reusable logic:

```tsx
// Data fetching hook
function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchData() {
      try {
        setLoading(true);
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error('Failed to fetch');
        const json = await response.json();
        setData(json);
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err as Error);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    return () => controller.abort();
  }, [url]);

  return { data, loading, error };
}

// Form state hook
function useForm<T extends Record<string, any>>(initialValues: T) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});

  const handleChange = useCallback((field: keyof T, value: any) => {
    setValues(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: undefined }));
  }, []);

  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
  }, [initialValues]);

  return { values, errors, handleChange, setErrors, reset };
}
```

### State Management

#### useState / useReducer

For component-local state:

```tsx
// Simple state
const [count, setCount] = useState(0);

// Complex state with reducer
interface State {
  items: Item[];
  loading: boolean;
  error: string | null;
}

type Action =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; payload: Item[] }
  | { type: 'FETCH_ERROR'; payload: string };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'FETCH_START':
      return { ...state, loading: true, error: null };
    case 'FETCH_SUCCESS':
      return { ...state, loading: false, items: action.payload };
    case 'FETCH_ERROR':
      return { ...state, loading: false, error: action.payload };
    default:
      return state;
  }
}

const [state, dispatch] = useReducer(reducer, initialState);
```

#### Context API

For shared state across components:

```tsx
// Context definition
interface AuthContextType {
  user: User | null;
  login: (credentials: Credentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Provider
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const login = async (credentials: Credentials) => {
    const user = await authService.login(credentials);
    setUser(user);
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook for consuming
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

#### Zustand (Recommended for Complex State)

```tsx
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CartStore {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (id: string) => void;
  clearCart: () => void;
  total: () => number;
}

export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (item) => set((state) => ({
        items: [...state.items, item]
      })),
      removeItem: (id) => set((state) => ({
        items: state.items.filter((i) => i.id !== id)
      })),
      clearCart: () => set({ items: [] }),
      total: () => get().items.reduce((sum, item) => sum + item.price, 0),
    }),
    { name: 'cart-storage' }
  )
);
```

### Performance Optimization

```tsx
// Memoize expensive calculations
const expensiveResult = useMemo(() => {
  return computeExpensiveValue(data);
}, [data]);

// Memoize callbacks
const handleClick = useCallback(() => {
  doSomething(id);
}, [id]);

// Memoize components
const MemoizedComponent = React.memo(function ExpensiveComponent({ data }) {
  return <div>{/* render expensive UI */}</div>;
});

// Lazy loading
const LazyComponent = React.lazy(() => import('./HeavyComponent'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <LazyComponent />
    </Suspense>
  );
}

// Virtual lists for large data
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
  });

  return (
    <div ref={parentRef} style={{ overflow: 'auto', height: '400px' }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {items[virtualItem.index]}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Testing with React Testing Library

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('Button', () => {
  it('renders with correct text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(<Button onClick={handleClick}>Click</Button>);
    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

// Testing async operations
describe('UserList', () => {
  it('fetches and displays users', async () => {
    server.use(
      http.get('/api/users', () => {
        return HttpResponse.json([
          { id: 1, name: 'John' },
          { id: 2, name: 'Jane' },
        ]);
      })
    );

    render(<UserList />);

    await waitFor(() => {
      expect(screen.getByText('John')).toBeInTheDocument();
      expect(screen.getByText('Jane')).toBeInTheDocument();
    });
  });
});

// Testing hooks
import { renderHook, act } from '@testing-library/react';

describe('useCounter', () => {
  it('increments counter', () => {
    const { result } = renderHook(() => useCounter());

    act(() => {
      result.current.increment();
    });

    expect(result.current.count).toBe(1);
  });
});
```

## Planning Process

### 1. Understand UI Requirements

- Identify user interactions and flows
- Define data requirements
- Determine state management needs
- Note responsive/accessibility requirements
- Identify reusable components

### 2. Design Component Hierarchy

```
App
├── Header
│   ├── Logo
│   ├── Navigation
│   └── UserMenu
├── Main
│   ├── Sidebar (conditional)
│   └── Content
│       ├── PageTitle
│       └── {Feature Components}
└── Footer
```

### 3. Plan State Architecture

- Identify what state is needed
- Determine where state should live
- Choose state management approach
- Plan data flow between components

### 4. Implementation Steps

Typical order:
1. Create type definitions
2. Build primitive UI components
3. Implement custom hooks
4. Create feature components
5. Add state management
6. Connect to API
7. Add tests
8. Optimize performance

### 5. Testing Strategy

- Unit tests for hooks and utilities
- Component tests for UI behavior
- Integration tests for features
- E2E tests for critical paths

## Output Spec Format

Create spec at `specs/{feature-slug}.md`:

```markdown
# {Feature Name} - React Implementation

## Overview

{Brief description of the UI feature}

## Component Hierarchy

```
FeatureRoot
├── Header
├── MainContent
│   ├── FilterBar
│   └── ItemList
│       └── ItemCard
└── Sidebar
```

## Components

### FeatureRoot
- **Props**: `initialData`, `onSave`
- **State**: `selectedItem`, `filters`
- **Responsibilities**: Orchestrate feature, manage state

### ItemCard
- **Props**: `item`, `onSelect`, `selected`
- **State**: None (presentational)
- **Responsibilities**: Display item, handle click

## State Management

### Local State
- `selectedItem: Item | null` - Currently selected item
- `filters: FilterState` - Active filters

### Context/Store
- `useFeatureStore` - Zustand store for feature data

## Custom Hooks

### useFeatureData
```typescript
function useFeatureData(filters: FilterState) {
  // Returns { data, loading, error, refetch }
}
```

## File Structure

- `src/features/feature/`
  - `components/` - Feature components
  - `hooks/` - Custom hooks
  - `types.ts` - Type definitions
  - `api.ts` - API calls
  - `store.ts` - State store
  - `index.ts` - Public exports

## Implementation Steps

1. **Create types** (types.ts)
   - Define interfaces
   - Export shared types

2. **Build base components** (components/)
   - ItemCard
   - FilterBar
   - Skeleton loaders

3. **Implement hooks** (hooks/)
   - useFeatureData
   - useFilters

4. **Create feature root** (FeatureRoot.tsx)
   - Compose components
   - Wire state

5. **Add tests** (__tests__/)
   - Component tests
   - Hook tests
   - Integration tests

## Testing Plan

### Unit Tests
- Hook behavior
- Utility functions

### Component Tests
- Rendering states
- User interactions
- Accessibility

### Integration Tests
- Feature workflows
- API integration
```

## Response Format

```
React Plan: {feature_name}

Spec created: specs/{feature-slug}.md

Component Structure:
- {N} components identified
- {M} custom hooks needed
- {K} state stores

Key Decisions:
- State: Zustand for global, useState for local
- Styling: Tailwind CSS / CSS Modules
- Testing: Vitest + RTL

File Structure:
- src/features/{feature}/
  - components/
  - hooks/
  - types.ts

Implementation: {N} steps defined

Next: Run `/implement specs/{feature-slug}.md`
```

## Anti-Patterns

Avoid these React mistakes:

- **Don't**: Create giant components
  **Do**: Extract into smaller, focused components

- **Don't**: Lift all state to the top
  **Do**: Keep state as close to usage as possible

- **Don't**: Use useEffect for everything
  **Do**: Derive state when possible, use proper hooks

- **Don't**: Skip memoization for expensive operations
  **Do**: Use useMemo/useCallback strategically

- **Don't**: Ignore TypeScript types
  **Do**: Define proper interfaces for props/state

- **Don't**: Mutate state directly
  **Do**: Always create new references

## Best Practices

- Use functional components with hooks
- Implement proper TypeScript types
- Extract reusable logic into custom hooks
- Keep components focused (single responsibility)
- Use composition over inheritance
- Implement error boundaries for resilience
- Add loading and error states
- Ensure accessibility (ARIA, keyboard nav)
- Optimize renders with React.memo when needed
- Use React DevTools for debugging
- Test behavior, not implementation
- Lazy load routes and heavy components
