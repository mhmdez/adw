# /plan_nextjs - Next.js Application Planner

Generate a comprehensive implementation plan for Next.js applications with full-stack considerations.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
description: Plan Next.js applications with SSR/SSG considerations
model: opus
```

## Purpose

Create detailed technical plans for Next.js applications. This planner understands Next.js 14+ patterns including App Router, Server Components, Server Actions, middleware, and the full-stack capabilities of modern Next.js.

## When to Use

- Building full-stack web applications
- Creating SEO-optimized sites with SSR/SSG
- Designing hybrid rendering strategies
- Planning API routes alongside UI
- Implementing authentication flows

## Input

$ARGUMENTS - Feature description or application requirements

Examples:
```
/plan_nextjs Add user authentication with NextAuth
/plan_nextjs Create e-commerce product pages with ISR
/plan_nextjs Implement real-time dashboard with streaming
```

## Next.js-Specific Knowledge

### App Router Structure (Next.js 14+)

```
app/
├── layout.tsx              # Root layout (applies to all pages)
├── page.tsx                # Home page (/)
├── loading.tsx             # Loading UI
├── error.tsx               # Error boundary
├── not-found.tsx           # 404 page
├── globals.css             # Global styles
├── (auth)/                 # Route group (no URL segment)
│   ├── layout.tsx          # Auth layout
│   ├── login/
│   │   └── page.tsx        # /login
│   └── register/
│       └── page.tsx        # /register
├── dashboard/
│   ├── layout.tsx          # Dashboard layout
│   ├── page.tsx            # /dashboard
│   ├── loading.tsx         # Dashboard loading
│   └── settings/
│       └── page.tsx        # /dashboard/settings
├── api/                    # API routes
│   └── users/
│       └── route.ts        # /api/users
└── @modal/                 # Parallel route for modals
    └── (.)photo/[id]/
        └── page.tsx        # Intercepted route
```

### Server vs Client Components

```tsx
// Server Component (default) - runs on server only
// app/posts/page.tsx
export default async function PostsPage() {
  // Direct database/API access - no client bundle
  const posts = await db.posts.findMany();

  return (
    <div>
      {posts.map(post => (
        <PostCard key={post.id} post={post} />
      ))}
    </div>
  );
}

// Client Component - add "use client" directive
// components/LikeButton.tsx
'use client';

import { useState } from 'react';

export function LikeButton({ initialLikes }: { initialLikes: number }) {
  const [likes, setLikes] = useState(initialLikes);

  return (
    <button onClick={() => setLikes(l => l + 1)}>
      {likes} likes
    </button>
  );
}
```

### Data Fetching Patterns

```tsx
// Server Component with async/await
async function PostPage({ params }: { params: { id: string } }) {
  // Automatic deduplication - fetch same URL once
  const post = await fetch(`/api/posts/${params.id}`).then(r => r.json());
  return <Post data={post} />;
}

// With caching options
async function getUser(id: string) {
  const res = await fetch(`/api/users/${id}`, {
    next: {
      revalidate: 3600,  // Revalidate every hour (ISR)
      tags: ['user'],    // Cache tag for on-demand revalidation
    }
  });
  return res.json();
}

// Static generation
export async function generateStaticParams() {
  const posts = await getPosts();
  return posts.map((post) => ({ id: post.id }));
}

// Dynamic rendering
export const dynamic = 'force-dynamic'; // Always server-render

// Parallel data fetching
async function Dashboard() {
  // Start all fetches in parallel
  const [user, posts, stats] = await Promise.all([
    getUser(),
    getPosts(),
    getStats(),
  ]);

  return <DashboardContent user={user} posts={posts} stats={stats} />;
}
```

### Server Actions

```tsx
// app/actions.ts
'use server';

import { revalidatePath, revalidateTag } from 'next/cache';
import { redirect } from 'next/navigation';

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string;
  const content = formData.get('content') as string;

  // Validate
  if (!title || !content) {
    return { error: 'Missing required fields' };
  }

  // Database operation
  const post = await db.posts.create({
    data: { title, content },
  });

  // Revalidate cache
  revalidatePath('/posts');
  revalidateTag('posts');

  // Redirect
  redirect(`/posts/${post.id}`);
}

// Usage in Client Component
'use client';

import { createPost } from './actions';
import { useFormStatus, useFormState } from 'react-dom';

function SubmitButton() {
  const { pending } = useFormStatus();
  return <button disabled={pending}>{pending ? 'Creating...' : 'Create'}</button>;
}

export function CreatePostForm() {
  const [state, formAction] = useFormState(createPost, null);

  return (
    <form action={formAction}>
      <input name="title" required />
      <textarea name="content" required />
      {state?.error && <p className="error">{state.error}</p>}
      <SubmitButton />
    </form>
  );
}
```

### API Routes (Route Handlers)

```tsx
// app/api/posts/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const page = searchParams.get('page') || '1';

  const posts = await db.posts.findMany({
    skip: (parseInt(page) - 1) * 10,
    take: 10,
  });

  return NextResponse.json(posts);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const post = await db.posts.create({ data: body });
    return NextResponse.json(post, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to create post' },
      { status: 500 }
    );
  }
}

// app/api/posts/[id]/route.ts
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const post = await db.posts.findUnique({
    where: { id: params.id },
  });

  if (!post) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  return NextResponse.json(post);
}
```

### Middleware

```tsx
// middleware.ts (root of project)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Authentication check
  const token = request.cookies.get('token')?.value;

  if (!token && request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // Add headers
  const response = NextResponse.next();
  response.headers.set('x-custom-header', 'value');

  return response;
}

// Configure which paths middleware runs on
export const config = {
  matcher: [
    '/dashboard/:path*',
    '/api/:path*',
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
```

### Authentication with NextAuth.js

```tsx
// app/api/auth/[...nextauth]/route.ts
import NextAuth from 'next-auth';
import { authOptions } from '@/lib/auth';

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };

// lib/auth.ts
import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import GoogleProvider from 'next-auth/providers/google';

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const user = await validateCredentials(credentials);
        return user || null;
      },
    }),
  ],
  callbacks: {
    async session({ session, token }) {
      session.user.id = token.sub;
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
};

// Get session in Server Component
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

export default async function ProtectedPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/login');
  }

  return <div>Welcome {session.user.name}</div>;
}
```

### Streaming and Suspense

```tsx
// app/dashboard/page.tsx
import { Suspense } from 'react';

export default function DashboardPage() {
  return (
    <div>
      <h1>Dashboard</h1>

      {/* Instant shell, stream content */}
      <Suspense fallback={<StatsSkeleton />}>
        <Stats />
      </Suspense>

      <Suspense fallback={<ChartSkeleton />}>
        <RevenueChart />
      </Suspense>

      <Suspense fallback={<TableSkeleton />}>
        <RecentOrders />
      </Suspense>
    </div>
  );
}

// Components fetch their own data
async function Stats() {
  const stats = await getStats(); // Slow fetch
  return <StatsGrid data={stats} />;
}
```

### Image Optimization

```tsx
import Image from 'next/image';

export function ProductImage({ src, alt }: { src: string; alt: string }) {
  return (
    <Image
      src={src}
      alt={alt}
      width={500}
      height={300}
      placeholder="blur"
      blurDataURL="/placeholder.jpg"
      priority={false}  // Set true for LCP images
      sizes="(max-width: 768px) 100vw, 50vw"
    />
  );
}
```

### Metadata and SEO

```tsx
// app/posts/[id]/page.tsx
import { Metadata } from 'next';

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const post = await getPost(params.id);

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [{ url: post.coverImage }],
    },
    twitter: {
      card: 'summary_large_image',
    },
  };
}

// Static metadata
export const metadata: Metadata = {
  title: {
    template: '%s | My Site',
    default: 'My Site',
  },
  description: 'Welcome to my site',
};
```

## Planning Process

### 1. Understand Rendering Requirements

- Which pages need SSR (dynamic, personalized)?
- Which can be SSG (static, cacheable)?
- Which need ISR (semi-static, periodic updates)?
- Which need streaming (slow data sources)?

### 2. Design Route Structure

```
Sitemap:
/                    → Static (SSG)
/products            → ISR (revalidate: 3600)
/products/[id]       → ISR with generateStaticParams
/cart                → Dynamic (user-specific)
/checkout            → Dynamic (secure, user-specific)
/dashboard           → Dynamic (authenticated)
/api/products        → Route handler
```

### 3. Plan Component Boundaries

- Server Components: Data fetching, sensitive logic
- Client Components: Interactivity, state, browser APIs
- Shared Components: UI primitives, layouts

### 4. Implementation Steps

Typical order:
1. Set up project structure
2. Create layouts and route groups
3. Implement Server Components with data fetching
4. Add Client Components for interactivity
5. Create Server Actions for mutations
6. Add API routes if needed
7. Implement authentication
8. Add middleware for protection
9. Optimize with caching and streaming
10. Add tests

## Output Spec Format

Create spec at `specs/{feature-slug}.md`:

```markdown
# {Feature Name} - Next.js Implementation

## Overview

{Brief description of the feature}

## Route Structure

| Route | Type | Rendering | Notes |
|-------|------|-----------|-------|
| / | Page | SSG | Home page |
| /posts | Page | ISR | Revalidate: 3600 |
| /posts/[id] | Dynamic | ISR | generateStaticParams |
| /dashboard | Page | Dynamic | Auth required |
| /api/posts | API | - | CRUD operations |

## Components

### Server Components
- `PostList` - Fetches and displays posts
- `PostDetail` - Single post view

### Client Components
- `LikeButton` - Interactive like functionality
- `CommentForm` - User input form

## Data Flow

1. User visits /posts
2. Server renders PostList
3. Client hydrates interactive parts
4. User clicks like → Server Action → Revalidate

## File Structure

```
app/
├── layout.tsx
├── page.tsx
├── posts/
│   ├── page.tsx
│   └── [id]/
│       └── page.tsx
├── api/
│   └── posts/
│       └── route.ts
└── actions/
    └── posts.ts
```

## Implementation Steps

1. **Create route structure**
   - app/posts/page.tsx
   - app/posts/[id]/page.tsx

2. **Implement Server Components**
   - PostList with data fetching
   - PostDetail with caching

3. **Add Client Components**
   - LikeButton with optimistic updates
   - CommentForm with Server Actions

4. **Create Server Actions**
   - createPost
   - likePost
   - addComment

5. **Add API routes** (if needed)
   - GET /api/posts
   - POST /api/posts

6. **Configure caching**
   - ISR for post pages
   - Tags for revalidation

## Caching Strategy

- Static pages: Build time generation
- Post list: ISR with 1-hour revalidate
- Individual posts: ISR with on-demand revalidation
- User data: No cache (dynamic)

## Testing Plan

### Unit Tests
- Server Actions
- Utility functions

### Integration Tests
- Page rendering
- API routes
- Data fetching

### E2E Tests
- User flows
- Authentication
```

## Response Format

```
Next.js Plan: {feature_name}

Spec created: specs/{feature-slug}.md

Route Structure:
- {N} pages defined
- {M} API routes
- {K} Server Actions

Rendering Strategy:
- SSG: /, /about
- ISR: /posts, /products
- Dynamic: /dashboard, /cart

Key Decisions:
- Auth: NextAuth.js with JWT
- Database: Prisma + PostgreSQL
- Styling: Tailwind CSS

File Structure:
- app/{feature}/
  - page.tsx (Server Component)
  - components/ (Client when needed)
  - actions.ts (Server Actions)

Implementation: {N} steps defined

Next: Run `/implement specs/{feature-slug}.md`
```

## Anti-Patterns

Avoid these Next.js mistakes:

- **Don't**: Add "use client" to everything
  **Do**: Keep components server-side by default

- **Don't**: Fetch data in Client Components
  **Do**: Pass data as props from Server Components

- **Don't**: Use getServerSideProps in App Router
  **Do**: Use async Server Components

- **Don't**: Ignore caching configurations
  **Do**: Set appropriate revalidate times

- **Don't**: Put sensitive data in Client Components
  **Do**: Keep secrets in Server Components/Actions

- **Don't**: Skip loading and error states
  **Do**: Add loading.tsx and error.tsx

## Best Practices

- Default to Server Components
- Use Suspense for streaming
- Implement parallel data fetching
- Configure proper caching (ISR, tags)
- Use Server Actions for mutations
- Add proper TypeScript types
- Implement proper error boundaries
- Optimize images with next/image
- Use proper metadata for SEO
- Protect sensitive routes with middleware
- Colocate related files in route folders
- Use route groups for organization
