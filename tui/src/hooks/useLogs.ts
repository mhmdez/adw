import { useState, useCallback } from 'react';

export interface LogEntry {
  timestamp: Date;
  type: 'user' | 'assistant' | 'system' | 'error' | 'tool' | 'agent';
  message: string;
  agentId?: string;
  taskId?: string;
  subtaskId?: string;
}

export function useLogs(maxLogs = 100): [LogEntry[], (entry: Omit<LogEntry, 'timestamp'>) => void] {
  const [logs, setLogs] = useState<LogEntry[]>([
    { timestamp: new Date(), type: 'system', message: 'Welcome to ADW - AI Developer Workflow' },
    { timestamp: new Date(), type: 'system', message: 'Type /help for commands, or just start typing' },
    { timestamp: new Date(), type: 'system', message: '' },
  ]);

  const addLog = useCallback((entry: Omit<LogEntry, 'timestamp'>) => {
    setLogs(prev => {
      const newLogs = [...prev, { ...entry, timestamp: new Date() }];
      // Keep only last maxLogs entries
      return newLogs.slice(-maxLogs);
    });
  }, [maxLogs]);

  return [logs, addLog];
}
