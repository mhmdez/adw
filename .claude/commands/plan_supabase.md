# /plan_supabase - Supabase Application Planner

Generate a comprehensive implementation plan for Supabase-backed applications with database-first design.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
description: Plan Supabase applications with database-first design
model: opus
```

## Purpose

Create detailed technical plans for applications using Supabase. This planner understands Supabase-specific patterns including PostgreSQL schema design, Row Level Security (RLS), Edge Functions, Realtime subscriptions, and authentication.

## When to Use

- Building applications with Supabase backend
- Designing PostgreSQL database schemas
- Implementing row-level security policies
- Creating Edge Functions for custom logic
- Adding real-time features with subscriptions

## Input

$ARGUMENTS - Feature description or data requirements

Examples:
```
/plan_supabase Design user profiles with RLS
/plan_supabase Create multi-tenant SaaS schema
/plan_supabase Implement real-time chat system
```

## Supabase-Specific Knowledge

### Database Schema Design

```sql
-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Users table (extends auth.users)
create table public.profiles (
  id uuid references auth.users(id) primary key,
  username text unique not null,
  full_name text,
  avatar_url text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Organizations (multi-tenant)
create table public.organizations (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  slug text unique not null,
  created_at timestamptz default now()
);

-- Organization members
create table public.organization_members (
  id uuid primary key default uuid_generate_v4(),
  organization_id uuid references organizations(id) on delete cascade,
  user_id uuid references profiles(id) on delete cascade,
  role text check (role in ('owner', 'admin', 'member')) default 'member',
  created_at timestamptz default now(),
  unique(organization_id, user_id)
);

-- Posts with organization context
create table public.posts (
  id uuid primary key default uuid_generate_v4(),
  organization_id uuid references organizations(id) on delete cascade,
  author_id uuid references profiles(id) on delete set null,
  title text not null,
  content text,
  status text check (status in ('draft', 'published', 'archived')) default 'draft',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes for performance
create index posts_organization_id_idx on posts(organization_id);
create index posts_author_id_idx on posts(author_id);
create index posts_status_idx on posts(status) where status = 'published';

-- Updated_at trigger
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger profiles_updated_at
  before update on profiles
  for each row execute function update_updated_at();

create trigger posts_updated_at
  before update on posts
  for each row execute function update_updated_at();
```

### Row Level Security (RLS)

```sql
-- Enable RLS on tables
alter table profiles enable row level security;
alter table organizations enable row level security;
alter table organization_members enable row level security;
alter table posts enable row level security;

-- Profiles policies
create policy "Users can view their own profile"
  on profiles for select
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on profiles for update
  using (auth.uid() = id);

-- Organization policies (multi-tenant)
create policy "Members can view their organizations"
  on organizations for select
  using (
    exists (
      select 1 from organization_members
      where organization_id = organizations.id
        and user_id = auth.uid()
    )
  );

-- Helper function for organization access
create or replace function is_org_member(org_id uuid)
returns boolean as $$
  select exists (
    select 1 from organization_members
    where organization_id = org_id
      and user_id = auth.uid()
  );
$$ language sql security definer;

-- Helper function for organization role check
create or replace function has_org_role(org_id uuid, allowed_roles text[])
returns boolean as $$
  select exists (
    select 1 from organization_members
    where organization_id = org_id
      and user_id = auth.uid()
      and role = any(allowed_roles)
  );
$$ language sql security definer;

-- Posts policies using helper functions
create policy "Members can view org posts"
  on posts for select
  using (is_org_member(organization_id));

create policy "Members can create posts"
  on posts for insert
  with check (
    is_org_member(organization_id)
    and author_id = auth.uid()
  );

create policy "Authors and admins can update posts"
  on posts for update
  using (
    author_id = auth.uid()
    or has_org_role(organization_id, array['owner', 'admin'])
  );

create policy "Admins can delete posts"
  on posts for delete
  using (has_org_role(organization_id, array['owner', 'admin']));
```

### Client Usage (TypeScript)

```typescript
import { createClient } from '@supabase/supabase-js';
import type { Database } from './types/supabase';

// Initialize client
const supabase = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Authentication
async function signUp(email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: 'John Doe' }
    }
  });
  return { data, error };
}

async function signIn(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  });
  return { data, error };
}

// OAuth
async function signInWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`
    }
  });
  return { data, error };
}

// CRUD Operations
async function getPosts(orgId: string) {
  const { data, error } = await supabase
    .from('posts')
    .select(`
      *,
      author:profiles(id, username, avatar_url)
    `)
    .eq('organization_id', orgId)
    .eq('status', 'published')
    .order('created_at', { ascending: false });

  return { data, error };
}

async function createPost(post: Omit<Post, 'id' | 'created_at' | 'updated_at'>) {
  const { data, error } = await supabase
    .from('posts')
    .insert(post)
    .select()
    .single();

  return { data, error };
}

async function updatePost(id: string, updates: Partial<Post>) {
  const { data, error } = await supabase
    .from('posts')
    .update(updates)
    .eq('id', id)
    .select()
    .single();

  return { data, error };
}

async function deletePost(id: string) {
  const { error } = await supabase
    .from('posts')
    .delete()
    .eq('id', id);

  return { error };
}
```

### Realtime Subscriptions

```typescript
// Subscribe to changes
function subscribeToOrgPosts(orgId: string, onUpdate: (post: Post) => void) {
  const channel = supabase
    .channel(`org-${orgId}-posts`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'posts',
        filter: `organization_id=eq.${orgId}`
      },
      (payload) => {
        if (payload.eventType === 'INSERT') {
          onUpdate(payload.new as Post);
        } else if (payload.eventType === 'UPDATE') {
          onUpdate(payload.new as Post);
        } else if (payload.eventType === 'DELETE') {
          // Handle delete
        }
      }
    )
    .subscribe();

  // Return cleanup function
  return () => {
    supabase.removeChannel(channel);
  };
}

// Presence (online users)
function subscribeToPresence(roomId: string, userId: string) {
  const channel = supabase.channel(`room-${roomId}`)
    .on('presence', { event: 'sync' }, () => {
      const state = channel.presenceState();
      console.log('Online users:', Object.keys(state));
    })
    .on('presence', { event: 'join' }, ({ key, newPresences }) => {
      console.log('User joined:', key);
    })
    .on('presence', { event: 'leave' }, ({ key, leftPresences }) => {
      console.log('User left:', key);
    })
    .subscribe(async (status) => {
      if (status === 'SUBSCRIBED') {
        await channel.track({ user_id: userId, online_at: new Date().toISOString() });
      }
    });

  return () => supabase.removeChannel(channel);
}

// Broadcast (ephemeral messages)
function subscribeToBroadcast(roomId: string) {
  const channel = supabase.channel(`room-${roomId}`)
    .on('broadcast', { event: 'cursor' }, (payload) => {
      console.log('Cursor position:', payload);
    })
    .subscribe();

  const sendCursor = (x: number, y: number) => {
    channel.send({
      type: 'broadcast',
      event: 'cursor',
      payload: { x, y }
    });
  };

  return { cleanup: () => supabase.removeChannel(channel), sendCursor };
}
```

### Edge Functions

```typescript
// supabase/functions/send-notification/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  // Handle CORS
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    // Initialize Supabase client with service role
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Get auth user from request
    const authHeader = req.headers.get('Authorization')!;
    const { data: { user }, error: authError } = await supabase.auth.getUser(
      authHeader.replace('Bearer ', '')
    );

    if (authError || !user) {
      return new Response(
        JSON.stringify({ error: 'Unauthorized' }),
        { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Parse request body
    const { title, message, recipient_id } = await req.json();

    // Create notification
    const { data, error } = await supabase
      .from('notifications')
      .insert({
        title,
        message,
        user_id: recipient_id,
        sender_id: user.id
      })
      .select()
      .single();

    if (error) throw error;

    // Send push notification via external service
    // await sendPushNotification(recipient_id, title, message);

    return new Response(
      JSON.stringify({ success: true, notification: data }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
```

### Storage

```typescript
// Upload file
async function uploadFile(bucket: string, path: string, file: File) {
  const { data, error } = await supabase.storage
    .from(bucket)
    .upload(path, file, {
      cacheControl: '3600',
      upsert: false
    });

  return { data, error };
}

// Get public URL
function getPublicUrl(bucket: string, path: string) {
  const { data } = supabase.storage
    .from(bucket)
    .getPublicUrl(path);

  return data.publicUrl;
}

// Create signed URL (for private files)
async function getSignedUrl(bucket: string, path: string, expiresIn: number = 3600) {
  const { data, error } = await supabase.storage
    .from(bucket)
    .createSignedUrl(path, expiresIn);

  return { data, error };
}

// Storage policies (in SQL)
/*
create policy "Users can upload their own avatar"
  on storage.objects for insert
  with check (
    bucket_id = 'avatars'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "Anyone can view avatars"
  on storage.objects for select
  using (bucket_id = 'avatars');
*/
```

### Type Generation

```bash
# Generate TypeScript types from your database
npx supabase gen types typescript --project-id your-project-id > src/types/supabase.ts
```

```typescript
// src/types/supabase.ts (generated)
export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          username: string;
          full_name: string | null;
          avatar_url: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          username: string;
          full_name?: string | null;
          avatar_url?: string | null;
        };
        Update: {
          username?: string;
          full_name?: string | null;
          avatar_url?: string | null;
        };
      };
      // ... other tables
    };
  };
};
```

## Planning Process

### 1. Understand Data Requirements

- Identify entities and relationships
- Determine access patterns
- Note multi-tenancy requirements
- Identify real-time needs
- Plan file storage needs

### 2. Design Database Schema

```sql
-- Entity relationship diagram as SQL
-- Users → Organizations (many-to-many via members)
-- Organizations → Resources (one-to-many)
-- Users → Resources (owner relationship)
```

### 3. Plan Security Model

- Which tables need RLS?
- What are the access patterns?
- How to handle multi-tenancy?
- What helper functions are needed?

### 4. Implementation Steps

Typical order:
1. Create migration with schema
2. Add RLS policies
3. Create helper functions
4. Generate TypeScript types
5. Implement client library
6. Add realtime subscriptions
7. Create Edge Functions
8. Configure storage buckets
9. Test policies and access

## Output Spec Format

Create spec at `specs/{feature-slug}.md`:

```markdown
# {Feature Name} - Supabase Implementation

## Overview

{Brief description of the feature and data model}

## Database Schema

### Tables

| Table | Description | Key Columns |
|-------|-------------|-------------|
| profiles | User profiles | id, username, avatar_url |
| organizations | Tenant entities | id, name, slug |
| posts | Content items | id, org_id, author_id, title |

### Relationships

```
profiles ←→ organizations (via organization_members)
organizations → posts (one-to-many)
profiles → posts (author relationship)
```

### Migrations

```sql
-- Migration 001: Initial schema
create table profiles (
  id uuid references auth.users primary key,
  username text unique not null
);
```

## Row Level Security

### Access Patterns

| Table | Select | Insert | Update | Delete |
|-------|--------|--------|--------|--------|
| profiles | Own profile | Auth trigger | Own profile | N/A |
| posts | Org members | Org members | Author/Admin | Admin |

### Policies

```sql
-- Key policies for this feature
create policy "..." on posts for select using (...);
```

## Client Implementation

### Queries
- `getPosts(orgId)` - Fetch posts with author
- `createPost(data)` - Create new post
- `updatePost(id, data)` - Update existing

### Subscriptions
- `subscribeToOrgPosts(orgId)` - Real-time post updates

## Edge Functions

| Function | Purpose | Trigger |
|----------|---------|---------|
| send-notification | Notify users | Manual call |
| process-upload | Handle file uploads | Storage hook |

## File Structure

```
supabase/
├── migrations/
│   └── 001_initial_schema.sql
├── functions/
│   └── send-notification/
│       └── index.ts
└── seed.sql
src/
├── lib/
│   └── supabase.ts
└── types/
    └── supabase.ts
```

## Implementation Steps

1. **Create migrations** (supabase/migrations/)
   - Define tables
   - Add indexes
   - Create triggers

2. **Add RLS policies**
   - Enable RLS on tables
   - Create helper functions
   - Add policies

3. **Generate types**
   - Run type generation
   - Import in client

4. **Implement client** (src/lib/supabase.ts)
   - CRUD functions
   - Subscription helpers

5. **Add Edge Functions** (if needed)
   - Create function
   - Deploy

## Testing Plan

### Database Tests
- Schema validation
- RLS policy tests

### Integration Tests
- CRUD operations
- Realtime subscriptions
- Edge Functions
```

## Response Format

```
Supabase Plan: {feature_name}

Spec created: specs/{feature-slug}.md

Database Design:
- {N} tables defined
- {M} RLS policies
- {K} helper functions

Security Model:
- Multi-tenant: Yes/No
- RLS: Enabled on all tables
- Auth: Supabase Auth

Features:
- Realtime: {subscription points}
- Storage: {buckets needed}
- Edge Functions: {function count}

File Structure:
- supabase/migrations/
- supabase/functions/
- src/lib/supabase.ts

Implementation: {N} steps defined

Next: Run `/implement specs/{feature-slug}.md`
```

## Anti-Patterns

Avoid these Supabase mistakes:

- **Don't**: Skip RLS on sensitive tables
  **Do**: Enable RLS and create proper policies

- **Don't**: Use service role key in frontend
  **Do**: Use anon key with RLS

- **Don't**: Create complex joins in every query
  **Do**: Use database views for complex queries

- **Don't**: Ignore indexes
  **Do**: Add indexes for frequent query patterns

- **Don't**: Store secrets in Edge Functions code
  **Do**: Use environment variables

- **Don't**: Create policies that scan entire tables
  **Do**: Use indexed columns in policies

## Best Practices

- Design database-first
- Enable RLS on all user-accessible tables
- Use helper functions for complex policy logic
- Generate TypeScript types from schema
- Use foreign key constraints
- Add appropriate indexes
- Use triggers for updated_at timestamps
- Test policies thoroughly
- Use views for complex joins
- Leverage realtime for live updates
- Keep Edge Functions focused and small
- Configure proper CORS for functions
- Use storage policies for file access control
