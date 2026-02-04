import { useState, useCallback, useEffect } from 'react';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { watch } from 'chokidar';

export interface Subtask {
  id: string;
  title: string;
  status: 'pending' | 'done';
}

export interface Task {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'done' | 'failed' | 'blocked';
  activity?: string;
  subtasks?: Subtask[];
  tags?: string[];
}

function generateId(): string {
  return Math.random().toString(16).slice(2, 10);
}

function extractTags(text: string): { cleaned: string; tags: string[] } {
  const match = text.match(/\s*\{([^}]+)\}\s*$/);
  if (!match) {
    return { cleaned: text.trim(), tags: [] };
  }
  const tagBlock = match[1] ?? '';
  const tags = tagBlock
    .split(',')
    .map(tag => tag.trim())
    .filter(Boolean);
  const cleaned = text.slice(0, match.index).trim();
  return { cleaned, tags };
}

function formatTags(tags: string[] | undefined): string {
  if (!tags || tags.length === 0) {
    return '';
  }
  return ` {${tags.join(', ')}}`;
}

function statusToEmoji(status: Task['status']): string {
  switch (status) {
    case 'done':
      return '✅';
    case 'failed':
      return '❌';
    case 'blocked':
      return '⏰';
    case 'in_progress':
      return '🟡';
    default:
      return ' ';
  }
}

function statusToCheckbox(status: Task['status']): string {
  switch (status) {
    case 'done':
      return 'x';
    case 'failed':
      return '!';
    case 'blocked':
      return '-';
    default:
      return ' ';
  }
}

function parseTasks(content: string): Task[] {
  const tasks: Task[] = [];
  const lines = content.split('\n');
  let currentTask: Task | null = null;
  let counter = 1;

  const legacyPattern = /^\[([^\]]*)\]\s*(.+)$/;
  const listTaskPattern = /^-\s+\[([ xX\-!])\]\s+(?:([A-Z]+-\d+):\s+)?(.+?)(?:\s+\((pending|in_progress|done|blocked|failed)\))?\s*$/;
  const subtaskPattern = /^\s+-\s+\[([ xX])\]\s+(.+)$/;

  for (const line of lines) {
    const listMatch = line.match(listTaskPattern);
    if (listMatch) {
      const [, checkbox, explicitId, title, explicitStatus] = listMatch;
      let status: Task['status'] = 'pending';
      if (explicitStatus) {
        status = explicitStatus as Task['status'];
      } else if (checkbox === 'x' || checkbox === 'X') {
        status = 'done';
      } else if (checkbox === '-') {
        status = 'blocked';
      } else if (checkbox === '!') {
        status = 'failed';
      }

      const { cleaned, tags } = extractTags(title);
      const id = explicitId || `TASK-${String(counter++).padStart(3, '0')}`;
      currentTask = { id, description: cleaned, status, subtasks: [], tags };
      tasks.push(currentTask);
      continue;
    }

    const legacyMatch = line.match(legacyPattern);
    if (legacyMatch) {
      const [, statusPart, description] = legacyMatch;
      const trimmedStatus = statusPart.trim();

      let status: Task['status'] = 'pending';
      let id = '';

      if (trimmedStatus === '') {
        status = 'pending';
        id = generateId();
      } else if (trimmedStatus === '⏰') {
        status = 'blocked';
        id = generateId();
      } else {
        const parts = trimmedStatus.split(',').map(s => s.trim());
        const emoji = parts[0];
        id = parts[1] || generateId();

        if (emoji === '✅' || emoji === '✓') {
          status = 'done';
        } else if (emoji === '🟡' || emoji === '⏳') {
          status = 'in_progress';
        } else if (emoji === '❌' || emoji === '✗') {
          status = 'failed';
        } else if (emoji === '⏰') {
          status = 'blocked';
        }
      }

      const { cleaned, tags } = extractTags(description);
      currentTask = { id, description: cleaned, status, subtasks: [], tags };
      tasks.push(currentTask);
      continue;
    }

    const subtaskMatch = line.match(subtaskPattern);
    if (subtaskMatch && currentTask) {
      const [, checkbox, title] = subtaskMatch;
      const subtaskStatus: Subtask['status'] = (checkbox === 'x' || checkbox === 'X') ? 'done' : 'pending';
      const subtask: Subtask = {
        id: `${currentTask.id}-${(currentTask.subtasks?.length ?? 0) + 1}`,
        title: title.trim(),
        status: subtaskStatus,
      };
      currentTask.subtasks = [...(currentTask.subtasks ?? []), subtask];
    }
  }

  return tasks;
}

export function useTasks(cwd: string) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const tasksFile = join(cwd, 'tasks.md');

  const reload = useCallback(() => {
    if (!existsSync(tasksFile)) {
      setTasks([]);
      return;
    }

    try {
      const content = readFileSync(tasksFile, 'utf-8');
      setTasks(parseTasks(content));
    } catch {
      setTasks([]);
    }
  }, [tasksFile]);

  // Initial load
  useEffect(() => {
    reload();
  }, [reload]);

  // Watch for changes
  useEffect(() => {
    const watcher = watch(tasksFile, { ignoreInitial: true });
    watcher.on('change', reload);
    return () => { watcher.close(); };
  }, [tasksFile, reload]);

  const addTask = useCallback((description: string, tags: string[] = []): Task => {
    const id = generateId();
    const task: Task = { id, description, status: 'in_progress', subtasks: [], tags };

    // Read current content
    let content = '';
    if (existsSync(tasksFile)) {
      content = readFileSync(tasksFile, 'utf-8');
    } else {
      content = '# Tasks\n\n';
    }

    // Append task
    content = content.trimEnd() + `\n[🟡, ${id}] ${description}${formatTags(tags)}\n`;
    writeFileSync(tasksFile, content);

    reload();
    return task;
  }, [tasksFile, reload]);

  const updateTask = useCallback((id: string, updates: Partial<Task>) => {
    setTasks(prev => prev.map(t =>
      t.id === id ? { ...t, ...updates } : t
    ));
  }, []);

  const updateTaskInFile = useCallback((id: string, updates: Partial<Task>) => {
    if (!existsSync(tasksFile)) {
      return false;
    }

    const content = readFileSync(tasksFile, 'utf-8');
    const lines = content.split('\n');
    let updated = false;

    const legacyPattern = /^\[([^\]]*)\]\s*(.+)$/;
    const listPattern = /^-\s+\[([ xX\-!])\]\s+(?:([A-Z]+-\d+):\s+)?(.+?)(?:\s+\((pending|in_progress|done|blocked|failed)\))?\s*$/;

    const nextLines = lines.map(line => {
      const legacyMatch = line.match(legacyPattern);
      if (legacyMatch) {
        const statusPart = legacyMatch[1];
        const description = legacyMatch[2];
        const parts = statusPart.split(',').map(part => part.trim());
        const idCandidate = parts[1];
        if (idCandidate === id) {
          const { cleaned, tags } = extractTags(description);
          const nextDescription = updates.description ?? cleaned;
          const nextTags = updates.tags ?? tags;
          const emoji = updates.status ? statusToEmoji(updates.status) : (parts[0] || ' ');
          updated = true;
          return `[${emoji}, ${id}] ${nextDescription}${formatTags(nextTags)}`;
        }
      }

      const listMatch = line.match(listPattern);
      if (listMatch) {
        const [, checkbox, explicitId, title, explicitStatus] = listMatch;
        if (explicitId === id) {
          const { cleaned, tags } = extractTags(title);
          const nextDescription = updates.description ?? cleaned;
          const nextTags = updates.tags ?? tags;
          const nextStatus = updates.status ?? (explicitStatus as Task['status'] | undefined);
          const checkboxValue = nextStatus ? statusToCheckbox(nextStatus) : checkbox;
          const statusSuffix = explicitStatus ? ` (${nextStatus ?? explicitStatus})` : '';
          updated = true;
          return `- [${checkboxValue}] ${explicitId}: ${nextDescription}${formatTags(nextTags)}${statusSuffix}`;
        }
      }

      return line;
    });

    if (updated) {
      writeFileSync(tasksFile, nextLines.join('\n'));
      reload();
    }

    return updated;
  }, [tasksFile, reload]);

  const setTaskStatus = useCallback((id: string, status: Task['status']) => {
    updateTaskInFile(id, { status });
  }, [updateTaskInFile]);

  const setTaskTags = useCallback((id: string, tags: string[]) => {
    updateTaskInFile(id, { tags });
  }, [updateTaskInFile]);

  return { tasks, reload, addTask, updateTask, setTaskStatus, setTaskTags };
}
