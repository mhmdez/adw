# /plan_vite_vue - Generate Vite + Vue 3 Application

Generate a complete, production-ready Vue 3 application with TypeScript and Vite.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Generate Vite + Vue 3 application
model: sonnet
```

## Purpose

Create a modern Vue 3 application scaffolded with Vite, TypeScript, and best practices. This prototype generator creates a complete project structure with routing, state management, components, and development tooling configured.

## When to Use

- Rapid prototyping of Vue 3 applications
- Creating new frontend projects with modern tooling
- Scaffolding Vue apps with best practices
- Starting a new UI project with TypeScript support

## Input

$ARGUMENTS - Application name and optional features

- **App name**: Name for the application (e.g., "my-app", "dashboard")
- **Features**: Optional comma-separated features (router, pinia, vitest)

Examples:
```
/plan_vite_vue my-app
/plan_vite_vue dashboard router,pinia,vitest
/plan_vite_vue admin-panel router,pinia
```

## Process

### 1. Parse Input

Extract from arguments:
- Application name (required)
- Feature flags: router, pinia, vitest, eslint
- Output directory: `apps/{app_name}/`

Defaults if not specified:
- Include Vue Router (navigation)
- Include basic components
- Include TypeScript configuration
- Include Vite dev server setup

### 2. Create Todo List

Use TodoWrite to track generation:
- Create project directory structure
- Generate package.json with dependencies
- Create Vite configuration
- Create TypeScript configuration
- Generate entry point (main.ts)
- Create root App.vue component
- Create sample components
- Generate index.html
- Create router configuration (if router enabled)
- Create store configuration (if pinia enabled)
- Create test setup (if vitest enabled)
- Generate README with usage instructions

### 3. Generate Project Structure

Create the following directory structure:

```
apps/{app_name}/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── env.d.ts
├── README.md
├── .gitignore
├── public/
│   └── favicon.ico
└── src/
    ├── main.ts
    ├── App.vue
    ├── assets/
    │   └── styles/
    │       └── main.css
    ├── components/
    │   ├── HelloWorld.vue
    │   └── TheHeader.vue
    ├── views/           # If router enabled
    │   ├── HomeView.vue
    │   └── AboutView.vue
    ├── router/          # If router enabled
    │   └── index.ts
    ├── stores/          # If pinia enabled
    │   └── counter.ts
    └── tests/           # If vitest enabled
        └── example.spec.ts
```

### 4. Generate Core Files

**package.json**:
```json
{
  "name": "{app_name}",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.1.0"
  }
}
```

Add conditional dependencies:
- Router: `"vue-router": "^4.5.0"`
- Pinia: `"pinia": "^2.3.0"`
- Vitest: `"vitest": "^3.0.0"`, `"@vue/test-utils": "^2.4.0"`, `"jsdom": "^26.0.0"`

**vite.config.ts**:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    strictPort: false
  }
})
```

**tsconfig.json**:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"]
}
```

**index.html**:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{App Name}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

**src/main.ts**:
```typescript
import { createApp } from 'vue'
import App from './App.vue'

const app = createApp(App)

// Router setup (if enabled)
// import router from './router'
// app.use(router)

// Pinia setup (if enabled)
// import { createPinia } from 'pinia'
// app.use(createPinia())

app.mount('#app')
```

**src/App.vue**:
```vue
<script setup lang="ts">
import HelloWorld from './components/HelloWorld.vue'
</script>

<template>
  <div id="app">
    <header>
      <h1>{{ title }}</h1>
    </header>
    <main>
      <HelloWorld msg="Welcome to your Vue 3 + Vite app" />
    </main>
  </div>
</template>

<script lang="ts">
export default {
  name: 'App',
  data() {
    return {
      title: '{App Name}'
    }
  }
}
</script>

<style scoped>
header {
  padding: 1rem;
  background: #42b983;
  color: white;
}
</style>
```

### 5. Generate Components

**src/components/HelloWorld.vue**:
```vue
<script setup lang="ts">
defineProps<{
  msg: string
}>()
</script>

<template>
  <div class="hello">
    <h2>{{ msg }}</h2>
    <p>
      Edit <code>src/components/HelloWorld.vue</code> to get started.
    </p>
  </div>
</template>

<style scoped>
.hello {
  padding: 2rem;
}

code {
  background-color: #f3f3f3;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-family: monospace;
}
</style>
```

### 6. Generate Router (if enabled)

**src/router/index.ts**:
```typescript
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/AboutView.vue')
    }
  ]
})

export default router
```

**src/views/HomeView.vue**:
```vue
<script setup lang="ts">
import HelloWorld from '@/components/HelloWorld.vue'
</script>

<template>
  <div class="home">
    <HelloWorld msg="Home Page" />
  </div>
</template>
```

### 7. Generate Store (if pinia enabled)

**src/stores/counter.ts**:
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCounterStore = defineStore('counter', () => {
  const count = ref(0)
  const doubleCount = computed(() => count.value * 2)

  function increment() {
    count.value++
  }

  function decrement() {
    count.value--
  }

  return { count, doubleCount, increment, decrement }
})
```

### 8. Generate Test Setup (if vitest enabled)

Add to **vite.config.ts**:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom'
  }
})
```

**src/tests/example.spec.ts**:
```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HelloWorld from '@/components/HelloWorld.vue'

describe('HelloWorld', () => {
  it('renders props.msg when passed', () => {
    const msg = 'Test message'
    const wrapper = mount(HelloWorld, {
      props: { msg }
    })
    expect(wrapper.text()).toContain(msg)
  })
})
```

### 9. Generate README

**README.md**:
```markdown
# {App Name}

Vue 3 application built with Vite and TypeScript.

## Features

- Vue 3 with Composition API
- TypeScript support
- Vite for fast development
{list enabled features}

## Setup

Install dependencies:

\`\`\`bash
npm install
\`\`\`

## Development

Run development server:

\`\`\`bash
npm run dev
\`\`\`

Open http://localhost:5173

## Build

Create production build:

\`\`\`bash
npm run build
\`\`\`

Preview production build:

\`\`\`bash
npm run preview
\`\`\`

## Testing

{if vitest enabled}
Run tests:

\`\`\`bash
npm test
\`\`\`

## Project Structure

\`\`\`
src/
├── main.ts          # Application entry point
├── App.vue          # Root component
├── components/      # Reusable components
├── views/           # Page components (if router)
├── router/          # Router configuration (if router)
├── stores/          # Pinia stores (if pinia)
└── assets/          # Static assets
\`\`\`

## Tech Stack

- Vue 3
- TypeScript
- Vite
{list other enabled features}
```

### 10. Generate .gitignore

**.gitignore**:
```
# Logs
logs
*.log
npm-debug.log*

# Dependencies
node_modules/

# Build
dist/
dist-ssr/

# Editor
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
.env.*.local
```

### 11. Verify Structure

Check that all files were created:
- Use Bash `ls` to verify directory structure
- Check that package.json is valid JSON
- Verify TypeScript configs are valid
- Ensure all imports use correct paths

### 12. Output Summary

Report:
- Application name and location
- Features enabled
- Files generated count
- Installation command
- Development command
- Next steps

## Example Usage

```
/plan_vite_vue my-dashboard

Generates apps/my-dashboard/ with basic Vue 3 + Vite setup.
```

```
/plan_vite_vue todo-app router,pinia

Generates apps/todo-app/ with router and state management.
```

```
/plan_vite_vue admin router,pinia,vitest

Generates apps/admin/ with full stack (router, store, tests).
```

## Response Format

```
Vite + Vue 3 application generated: {app_name}

Location: apps/{app_name}/

Features Enabled:
- Vue 3 with Composition API
- TypeScript support
- Vite build tool
{additional features if enabled}

Files Generated: {N} files
- package.json
- vite.config.ts
- tsconfig.json
- src/main.ts
- src/App.vue
- {list other key files}

Next Steps:

1. Install dependencies:
   cd apps/{app_name}
   npm install

2. Start development server:
   npm run dev

3. Open http://localhost:5173

Project is ready for development!
```

## Notes

- **Model**: Use Sonnet for generation (straightforward scaffolding)
- **Dependencies**: Use latest stable versions
- **Best Practices**: Follow Vue 3 Composition API patterns
- **TypeScript**: Strict mode enabled by default
- **Path Aliases**: Configure `@/` alias for `src/`
- **Dev Server**: Auto-open browser, HMR enabled
- **Production**: Optimized builds with tree-shaking
- **Testing**: Vitest for unit tests if enabled
- **Router**: Hash mode for simpler deployment, or history mode with server config

## Feature Flags

Available feature flags:

- **router**: Add Vue Router for navigation
- **pinia**: Add Pinia for state management
- **vitest**: Add Vitest for unit testing
- **eslint**: Add ESLint for code quality (future)

Default includes:
- TypeScript
- Vite
- Basic components
- CSS support

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Use Options API in new code
  **Do**: Use Composition API with `<script setup>`

- **Don't**: Hardcode API URLs
  **Do**: Use environment variables

- **Don't**: Skip TypeScript types
  **Do**: Define props and emits with types

- **Don't**: Create monolithic components
  **Do**: Break into smaller, reusable pieces

- **Don't**: Ignore build warnings
  **Do**: Address TypeScript and Vite warnings

## Best Practices

Follow these patterns:

- Use `<script setup>` for cleaner component syntax
- Define prop types with TypeScript
- Use composables for shared logic
- Keep components focused and single-purpose
- Use path aliases (`@/`) for clean imports
- Leverage Vue 3 reactivity system
- Use `defineProps`, `defineEmits` for type safety
- Structure stores with Composition API pattern

## Integration

This command is used for:
- **Prototype workflow**: /plan_vite_vue → develop → deploy
- **ADW workflows**: Can be called via `adw prototype vite_vue {name}`
- **Standalone**: Direct invocation for rapid scaffolding

The generated project is standalone and ready for development.

## Success Criteria

Generation is complete when:
- [ ] All files created in correct structure
- [ ] package.json has valid dependencies
- [ ] TypeScript configs are valid
- [ ] Entry point (main.ts) is correct
- [ ] App.vue component is valid
- [ ] Sample components included
- [ ] index.html loads correctly
- [ ] README has usage instructions
- [ ] .gitignore includes standard exclusions
- [ ] Feature-specific files generated (if enabled)
- [ ] Summary report provided

## Customization

After generation, customize:
- Update app title in index.html
- Modify color scheme in CSS
- Add custom components
- Configure API endpoints
- Set up authentication
- Add UI library (Vuetify, PrimeVue, etc.)
- Configure build options
- Add environment variables

## Common Additions

Typical next steps after generation:

- Add UI framework (Tailwind, Bootstrap, Vuetify)
- Set up API client (Axios, Fetch)
- Add authentication (JWT, OAuth)
- Configure routing guards
- Add form validation (VeeValidate)
- Set up internationalization (vue-i18n)
- Add analytics
- Configure PWA support

## Troubleshooting

Common issues and solutions:

**Port already in use**:
- Vite will auto-increment port (5174, 5175, etc.)
- Or configure specific port in vite.config.ts

**TypeScript errors**:
- Run `npm run build` to check for errors
- Ensure all imports use `.vue` extension in imports

**HMR not working**:
- Check Vite dev server is running
- Clear browser cache
- Restart dev server

**Build fails**:
- Check TypeScript errors with `vue-tsc --noEmit`
- Verify all dependencies installed
- Clear node_modules and reinstall
