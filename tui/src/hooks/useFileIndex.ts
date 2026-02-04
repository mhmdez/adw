import { useCallback, useEffect, useState } from 'react';
import { readdir } from 'fs/promises';
import { join } from 'path';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

const DEFAULT_IGNORES = new Set([
  '.git',
  'node_modules',
  '.venv',
  '.adw',
  '.pytest_cache',
  'dist',
  'build',
  'coverage',
  'agents',
  'bundle',
  '.idea',
  '.vscode',
]);

async function listGitFiles(cwd: string): Promise<string[] | null> {
  try {
    const inside = await execFileAsync('git', ['rev-parse', '--is-inside-work-tree'], { cwd });
    if (inside.stdout.trim() !== 'true') {
      return null;
    }
    const tracked = await execFileAsync('git', ['ls-files'], { cwd });
    const untracked = await execFileAsync('git', ['ls-files', '--others', '--exclude-standard'], { cwd });
    const files = [...tracked.stdout.split('\n'), ...untracked.stdout.split('\n')]
      .map(line => line.trim())
      .filter(Boolean);
    return Array.from(new Set(files));
  } catch {
    return null;
  }
}

async function scanFiles(
  cwd: string,
  maxFiles: number,
  maxDepth: number,
  ignores: Set<string>,
): Promise<string[]> {
  const results: string[] = [];

  async function walk(dir: string, depth: number) {
    if (results.length >= maxFiles || depth > maxDepth) {
      return;
    }
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (results.length >= maxFiles) {
        return;
      }
      const name = entry.name;
      const relative = dir === cwd ? name : join(dir.replace(cwd, '').replace(/^\//, ''), name);
      const rootName = name.split('/')[0] ?? name;
      if (ignores.has(rootName)) {
        continue;
      }
      const fullPath = join(dir, name);
      if (entry.isDirectory()) {
        await walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        results.push(relative);
      }
    }
  }

  await walk(cwd, 0);
  return results;
}

export function useFileIndex(cwd: string, maxFiles = 2000) {
  const [files, setFiles] = useState<string[]>([]);
  const [isIndexing, setIsIndexing] = useState(false);

  const refresh = useCallback(async () => {
    setIsIndexing(true);
    try {
      const gitFiles = await listGitFiles(cwd);
      if (gitFiles && gitFiles.length > 0) {
        setFiles(gitFiles.slice(0, maxFiles));
        return;
      }
      const scanned = await scanFiles(cwd, maxFiles, 8, DEFAULT_IGNORES);
      setFiles(scanned);
    } finally {
      setIsIndexing(false);
    }
  }, [cwd, maxFiles]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { files, isIndexing, refresh };
}
