import { useState, useCallback, useEffect } from 'react';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { watch } from 'chokidar';

export interface Task {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'done' | 'failed' | 'blocked';
  activity?: string;
}

function generateId(): string {
  return Math.random().toString(16).slice(2, 10);
}

function parseTasks(content: string): Task[] {
  const tasks: Task[] = [];
  const lines = content.split('\n');

  for (const line of lines) {
    // Match: [status, id] description or [status] description or [] description
    const match = line.match(/^\[([^\]]*)\]\s*(.+)$/);
    if (!match) continue;

    const [, statusPart, description] = match;
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
      // Parse [emoji, id] format
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

    tasks.push({ id, description: description.trim(), status });
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

  const addTask = useCallback((description: string): Task => {
    const id = generateId();
    const task: Task = { id, description, status: 'in_progress' };

    // Read current content
    let content = '';
    if (existsSync(tasksFile)) {
      content = readFileSync(tasksFile, 'utf-8');
    } else {
      content = '# Tasks\n\n';
    }

    // Append task
    content = content.trimEnd() + `\n[🟡, ${id}] ${description}\n`;
    writeFileSync(tasksFile, content);

    reload();
    return task;
  }, [tasksFile, reload]);

  const updateTask = useCallback((id: string, updates: Partial<Task>) => {
    setTasks(prev => prev.map(t =>
      t.id === id ? { ...t, ...updates } : t
    ));
  }, []);

  return { tasks, reload, addTask, updateTask };
}
