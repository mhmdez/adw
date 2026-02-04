import { useCallback, useEffect, useState } from 'react';
import { execFile } from 'child_process';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

function parseStatusLine(line: string): string {
  const trimmed = line.slice(3).trim();
  if (trimmed.includes(' -> ')) {
    const parts = trimmed.split(' -> ');
    return parts[1] ?? trimmed;
  }
  return trimmed;
}

export function useGitStatus(cwd: string, intervalMs = 5000) {
  const [files, setFiles] = useState<string[]>([]);
  const [isRepo, setIsRepo] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await execFileAsync('git', ['status', '--porcelain'], { cwd });
      const changed = result.stdout
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(parseStatusLine);
      setFiles(changed);
      setIsRepo(true);
      setLastUpdated(new Date());
    } catch {
      setIsRepo(false);
      setFiles([]);
    }
  }, [cwd]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [refresh, intervalMs]);

  return { files, isRepo, lastUpdated, refresh };
}
