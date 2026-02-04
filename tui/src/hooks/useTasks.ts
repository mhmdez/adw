import { useState, useCallback, useEffect } from 'react';
import { readFileSync, writeFileSync, existsSync, renameSync } from 'fs';
import { join, dirname } from 'path';
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
  adwId?: string;
}

const TASK_ID_REGEX = /\bTASK-\d+\b/;
const ADW_ID_REGEX = /^[a-f0-9]{8}$/i;

function hashString(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return hash.toString(16).padStart(8, '0').slice(0, 8);
}

function fallbackIdFromLine(line: string): string {
  return hashString(line);
}

function extractTaskId(text: string): string | undefined {
  const match = text.match(TASK_ID_REGEX);
  return match?.[0];
}

function splitTaskPrefix(text: string): { prefix: string; id?: string; description: string } {
  const match = text.match(/^(\s*(?:\*\*)?TASK-\d+(?:\*\*)?:\s*)(.*)$/);
  if (!match) {
    return { prefix: '', description: text.trim() };
  }
  const idMatch = match[1].match(TASK_ID_REGEX);
  return { prefix: match[1], id: idMatch?.[0], description: match[2].trim() };
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

function parseStatus(statusPart: string): Task['status'] {
  const trimmed = statusPart.trim();
  if (!trimmed) {
    return 'pending';
  }
  if (trimmed.includes('⏰') || trimmed.includes('blocked')) {
    return 'blocked';
  }
  if (trimmed.includes('🟡') || trimmed.includes('⏳')) {
    return 'in_progress';
  }
  if (trimmed.includes('✅') || trimmed.includes('✓')) {
    return 'done';
  }
  if (trimmed.includes('❌') || trimmed.includes('✗')) {
    return 'failed';
  }
  return 'pending';
}

function extractAdwId(statusPart: string): string | undefined {
  const parts = statusPart
    .split(',')
    .map(part => part.trim())
    .filter(Boolean);
  for (let i = parts.length - 1; i >= 0; i -= 1) {
    if (ADW_ID_REGEX.test(parts[i])) {
      return parts[i];
    }
  }
  return undefined;
}

function parseMarkerTokens(statusPart: string): { adwId?: string; commit?: string } {
  const parts = statusPart
    .split(',')
    .map(part => part.trim())
    .filter(Boolean);
  const others = parts.slice(1);
  let adwId: string | undefined;
  let commit: string | undefined;

  for (const token of others) {
    if (ADW_ID_REGEX.test(token)) {
      adwId = token;
    } else if (/^[a-f0-9]{7,40}$/i.test(token)) {
      commit = token;
    }
  }

  return { adwId, commit };
}

function buildMarker(status: Task['status'], adwId?: string, commit?: string): string {
  switch (status) {
    case 'pending':
      return '[ ]';
    case 'blocked':
      return '[⏰]';
    case 'in_progress':
      return adwId ? `[🟡, ${adwId}]` : '[🟡]';
    case 'done': {
      const parts = ['✅'];
      if (commit) {
        parts.push(commit);
      }
      if (adwId) {
        parts.push(adwId);
      }
      return `[${parts.join(', ')}]`;
    }
    case 'failed':
      return adwId ? `[❌, ${adwId}]` : '[❌]';
    default:
      return '[ ]';
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

function getNextTaskId(content: string): string {
  let maxNum = 0;
  const matches = content.match(/TASK-(\d+)/g) ?? [];
  for (const match of matches) {
    const num = Number(match.replace('TASK-', ''));
    if (!Number.isNaN(num)) {
      maxNum = Math.max(maxNum, num);
    }
  }
  return `TASK-${String(maxNum + 1).padStart(3, '0')}`;
}

function insertTaskLine(content: string, taskLine: string): string {
  if (content.includes('## Active Tasks')) {
    const parts = content.split('## Active Tasks', 1);
    const rest = content.slice(parts[0].length + '## Active Tasks'.length);
    const lines = rest.split('\n');
    let insertIdx = 0;
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (line.trim() && !line.trim().startsWith('<!--')) {
        insertIdx = i;
        break;
      }
      insertIdx = i + 1;
    }
    lines.splice(insertIdx, 0, taskLine);
    return parts[0] + '## Active Tasks' + lines.join('\n');
  }

  return content.trimEnd() + `\n\n## Active Tasks\n\n${taskLine}\n`;
}

function writeFileAtomic(path: string, content: string, backupContent?: string): void {
  const dir = dirname(path);
  const tempPath = join(dir, `.tmp-${Date.now()}-${process.pid}`);
  if (backupContent !== undefined) {
    const backupPath = `${path}.bak`;
    writeFileSync(backupPath, backupContent);
  }
  writeFileSync(tempPath, content);
  renameSync(tempPath, path);
}

function parseTasks(content: string): Task[] {
  const tasks: Task[] = [];
  const lines = content.split('\n');
  let currentTask: Task | null = null;
  let counter = 1;

  const legacyPattern = /^(\s*(?:-\s+)?)\[([^\]]*)\]\s*(.+)$/;
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
      const prefixInfo = splitTaskPrefix(cleaned);
      const idFromDesc = prefixInfo.id ?? extractTaskId(cleaned);
      const id = explicitId || idFromDesc || `TASK-${String(counter++).padStart(3, '0')}`;
      const description = prefixInfo.prefix ? prefixInfo.description : cleaned.trim();

      currentTask = { id, description, status, subtasks: [], tags };
      tasks.push(currentTask);
      continue;
    }

    const legacyMatch = line.match(legacyPattern);
    if (legacyMatch) {
      const [, , statusPart, rest] = legacyMatch;
      const status = parseStatus(statusPart);
      const adwId = extractAdwId(statusPart);

      const { cleaned, tags } = extractTags(rest);
      const prefixInfo = splitTaskPrefix(cleaned);
      const idFromDesc = prefixInfo.id ?? extractTaskId(cleaned);
      const id = idFromDesc || adwId || fallbackIdFromLine(line);
      const description = prefixInfo.prefix ? prefixInfo.description : cleaned.trim();

      currentTask = { id, description, status, subtasks: [], tags, adwId };
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
    let content = '';
    if (existsSync(tasksFile)) {
      content = readFileSync(tasksFile, 'utf-8');
    } else {
      content = '# Tasks\n\n## Active Tasks\n\n## Completed Tasks\n';
      writeFileAtomic(tasksFile, content);
    }

    const id = getNextTaskId(content);
    const task: Task = { id, description, status: 'pending', subtasks: [], tags };
    const taskLine = `[ ] **${id}**: ${description}${formatTags(tags)}`;

    const nextContent = insertTaskLine(content, taskLine);
    const backupContent = existsSync(tasksFile) ? content : undefined;
    writeFileAtomic(tasksFile, nextContent, backupContent);

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

    const legacyPattern = /^(\s*(?:-\s+)?)\[([^\]]*)\]\s*(.+)$/;
    const listPattern = /^-\s+\[([ xX\-!])\]\s+(?:([A-Z]+-\d+):\s+)?(.+?)(?:\s+\((pending|in_progress|done|blocked|failed)\))?\s*$/;

    const nextLines = lines.map(line => {
      const listMatch = line.match(listPattern);
      if (listMatch) {
        const [, checkbox, explicitId, title, explicitStatus] = listMatch;
        const { cleaned, tags } = extractTags(title);
        const prefixInfo = splitTaskPrefix(cleaned);
        const lineId = explicitId || prefixInfo.id || extractTaskId(cleaned);
        if (lineId === id) {
          const nextDescription = updates.description ?? (prefixInfo.prefix ? prefixInfo.description : cleaned.trim());
          const nextTags = updates.tags ?? tags;
          const nextStatus = updates.status ?? (explicitStatus as Task['status'] | undefined);
          const checkboxValue = nextStatus ? statusToCheckbox(nextStatus) : checkbox;
          const statusSuffix = explicitStatus ? ` (${nextStatus ?? explicitStatus})` : '';
          updated = true;

          const titlePrefix = prefixInfo.prefix;
          const titleText = `${titlePrefix}${nextDescription}`.trim();
          return `- [${checkboxValue}] ${explicitId ? `${explicitId}: ` : ''}${titleText}${formatTags(nextTags)}${statusSuffix}`;
        }
      }

      const legacyMatch = line.match(legacyPattern);
      if (legacyMatch) {
        const [, lead, statusPart, rest] = legacyMatch;
        const { cleaned, tags } = extractTags(rest);
        const prefixInfo = splitTaskPrefix(cleaned);
        const lineId = prefixInfo.id || extractTaskId(cleaned) || extractAdwId(statusPart);

        if (lineId === id) {
          const nextDescription = updates.description ?? (prefixInfo.prefix ? prefixInfo.description : cleaned.trim());
          const nextTags = updates.tags ?? tags;
          const { adwId, commit } = parseMarkerTokens(statusPart);
          const marker = updates.status ? buildMarker(updates.status, adwId, commit) : `[${statusPart}]`;
          const titlePrefix = prefixInfo.prefix;
          updated = true;
          return `${lead}${marker} ${titlePrefix}${nextDescription}${formatTags(nextTags)}`;
        }
      }

      return line;
    });

    if (updated) {
      writeFileAtomic(tasksFile, nextLines.join('\n'), content);
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

export const __test__ = {
  parseTasks,
  insertTaskLine,
  buildMarker,
  extractTags,
  splitTaskPrefix,
};
