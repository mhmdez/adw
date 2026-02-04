import { useState, useCallback, useRef } from 'react';
import { spawn as spawnProcess, ChildProcess } from 'child_process';
import { join } from 'path';
import { mkdirSync, existsSync, createWriteStream } from 'fs';
import { LogEntry } from './useLogs.js';

const ANSI_ESCAPE = /\x1b\[[0-9;]*m/g;
const MAX_FALLBACK_PROMPT_CHARS = 8000;

type AgentMode = 'adw' | 'fallback';

interface FallbackAgent {
  id: string;
  process: ChildProcess;
  description: string;
  startedAt: Date;
}

function stripAnsi(text: string): string {
  return text.replace(ANSI_ESCAPE, '');
}

function parseEventData(raw: unknown): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return { message: raw };
    }
  }
  if (typeof raw === 'object') {
    return raw as Record<string, unknown>;
  }
  return { message: String(raw) };
}

function formatEventMessage(eventType: string, data: Record<string, unknown>): string {
  const label = eventType.replace(/_/g, ' ');
  const message = typeof data.message === 'string' ? data.message : undefined;
  const toolName = typeof data.tool_name === 'string' ? data.tool_name : undefined;
  const status = typeof data.status === 'string' ? data.status : undefined;

  if (message) return `${label}: ${message}`;
  if (toolName) return `${label}: ${toolName}`;
  if (status) return `${label}: ${status}`;
  return label;
}

function eventLogType(eventType: string): LogEntry['type'] {
  if (eventType.includes('error') || eventType.includes('failed') || eventType.includes('safety')) {
    return 'error';
  }
  if (eventType.startsWith('tool_') || eventType.includes('tool')) {
    return 'tool';
  }
  if (eventType.startsWith('agent_')) {
    return 'agent';
  }
  if (eventType === 'user_prompt') {
    return 'user';
  }
  return 'system';
}

export function useAgents(cwd: string, addLog: (entry: Omit<LogEntry, 'timestamp'>) => void) {
  const daemonRef = useRef<ChildProcess | null>(null);
  const eventsRef = useRef<ChildProcess | null>(null);
  const eventsBufferRef = useRef('');
  const modeRef = useRef<AgentMode>('adw');
  const agentsRef = useRef<Map<string, FallbackAgent>>(new Map());

  const [daemonRunning, setDaemonRunning] = useState(false);
  const [agentMode, setAgentMode] = useState<AgentMode>('adw');
  const [agents, setAgents] = useState<Map<string, FallbackAgent>>(new Map());

  const setMode = (mode: AgentMode) => {
    modeRef.current = mode;
    setAgentMode(mode);
  };

  const stopEventStream = () => {
    if (eventsRef.current) {
      try {
        eventsRef.current.kill('SIGTERM');
      } catch {
        // ignore
      }
      eventsRef.current = null;
      eventsBufferRef.current = '';
    }
  };

  const stopDaemon = useCallback(() => {
    if (!daemonRef.current) {
      return false;
    }

    const proc = daemonRef.current;
    try {
      if (proc.pid) {
        process.kill(-proc.pid, 'SIGTERM');
      } else {
        proc.kill('SIGTERM');
      }
    } catch {
      try {
        proc.kill('SIGTERM');
      } catch {
        // ignore
      }
    }

    daemonRef.current = null;
    setDaemonRunning(false);
    stopEventStream();
    addLog({ type: 'system', message: 'Stopping ADW daemon...' });
    return true;
  }, [addLog]);

  const enableFallback = (reason: string) => {
    if (modeRef.current === 'fallback') {
      return;
    }
    setMode('fallback');
    setDaemonRunning(false);
    if (daemonRef.current) {
      try {
        daemonRef.current.kill('SIGTERM');
      } catch {
        // ignore
      }
      daemonRef.current = null;
    }
    stopEventStream();
    addLog({ type: 'error', message: reason });
    addLog({ type: 'system', message: 'Falling back to raw Claude execution.' });
  };

  const handleAdwEvent = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    try {
      const event = JSON.parse(trimmed) as {
        event_type?: string;
        task_id?: string | null;
        data?: unknown;
      };

      const eventType = event.event_type ?? 'info';
      const data = parseEventData(event.data);
      const message = formatEventMessage(eventType, data);
      const logType = eventLogType(eventType);
      const taskId = event.task_id ?? undefined;

      if (eventType === 'info' && !data.message) {
        return;
      }

      addLog({
        type: logType,
        message,
        taskId,
      });
    } catch {
      // ignore malformed lines
    }
  };

  const startEventStream = () => {
    if (eventsRef.current || modeRef.current !== 'adw') {
      return;
    }

    const proc = spawnProcess('adw', ['events', '--follow', '--json'], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    eventsRef.current = proc;

    proc.stdout?.on('data', (data: Buffer) => {
      const text = stripAnsi(data.toString());
      eventsBufferRef.current += text;
      const lines = eventsBufferRef.current.split('\n');
      eventsBufferRef.current = lines.pop() ?? '';
      for (const line of lines) {
        handleAdwEvent(line);
      }
    });

    proc.stderr?.on('data', (data: Buffer) => {
      const msg = stripAnsi(data.toString()).trim();
      if (msg) {
        addLog({ type: 'error', message: `ADW events: ${msg}` });
      }
    });

    proc.on('close', () => {
      eventsRef.current = null;
      eventsBufferRef.current = '';
    });

    proc.on('error', (error) => {
      eventsRef.current = null;
      eventsBufferRef.current = '';
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        enableFallback('ADW CLI not found when starting event stream.');
      } else {
        addLog({ type: 'error', message: `ADW event stream failed: ${error.message}` });
      }
    });
  };

  const startDaemon = useCallback(() => {
    if (modeRef.current === 'fallback') {
      return;
    }
    if (daemonRef.current) {
      return;
    }

    const tasksFile = join(cwd, 'tasks.md');
    if (!existsSync(tasksFile)) {
      addLog({ type: 'error', message: 'tasks.md not found. Run adw init first.' });
      return;
    }

    const proc = spawnProcess('adw', [
      'run',
      '--tasks-file', tasksFile,
      '--no-notifications',
    ], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
    });

    daemonRef.current = proc;
    setDaemonRunning(true);
    setMode('adw');

    if (proc.pid) {
      addLog({ type: 'system', message: `ADW daemon started (pid ${proc.pid})` });
    } else {
      addLog({ type: 'system', message: 'ADW daemon started' });
    }

    startEventStream();

    const handleOutput = (data: Buffer, type: 'system' | 'error') => {
      const text = stripAnsi(data.toString());
      const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
      for (const line of lines) {
        addLog({ type, message: line });
      }
    };

    proc.stdout?.on('data', (data: Buffer) => handleOutput(data, 'system'));
    proc.stderr?.on('data', (data: Buffer) => handleOutput(data, 'error'));

    proc.on('close', (code) => {
      daemonRef.current = null;
      setDaemonRunning(false);
      stopEventStream();

      if (code === 0) {
        addLog({ type: 'system', message: 'ADW daemon stopped' });
      } else {
        addLog({ type: 'error', message: `ADW daemon exited (code ${code ?? 'unknown'})` });
        enableFallback('ADW daemon exited unexpectedly.');
      }
    });

    proc.on('error', (error) => {
      daemonRef.current = null;
      setDaemonRunning(false);
      stopEventStream();
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        enableFallback('ADW CLI not found.');
      } else {
        addLog({ type: 'error', message: `Failed to start ADW daemon: ${error.message}` });
        enableFallback('ADW daemon failed to start.');
      }
    });

    proc.unref();
  }, [cwd, addLog]);

  const spawnFallbackAgent = useCallback((id: string, description: string) => {
    const agentDir = join(cwd, 'agents', id, 'prompt');
    if (!existsSync(agentDir)) {
      mkdirSync(agentDir, { recursive: true });
    }

    const outputFile = join(agentDir, 'cc_raw_output.jsonl');
    const outputStream = createWriteStream(outputFile);

    let prompt = `Task ID: ${id}\n\nPlease complete this task:\n\n${description}\n\nWork in the current directory. When done, summarize what you accomplished.`;

    if (prompt.length > MAX_FALLBACK_PROMPT_CHARS) {
      prompt = prompt.slice(0, MAX_FALLBACK_PROMPT_CHARS) + '\n\n[Prompt truncated]';
      addLog({
        type: 'error',
        message: `Prompt for ${id} was truncated for CLI safety. Consider using a shorter description.`,
        taskId: id,
      });
    }

    const proc = spawnProcess('claude', [
      '--model', 'sonnet',
      '--output-format', 'stream-json',
      '--print', prompt,
    ], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
    });

    addLog({ type: 'system', message: `Fallback agent started for ${id.slice(0, 8)}`, taskId: id });

    proc.stdout?.on('data', (data: Buffer) => {
      outputStream.write(data);

      const lines = data.toString().split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const event = JSON.parse(line);
          handleClaudeEvent(id, event, addLog);
        } catch {
          // ignore parse errors
        }
      }
    });

    proc.stderr?.on('data', (data: Buffer) => {
      const msg = data.toString().trim();
      if (msg) {
        addLog({ type: 'error', message: msg, agentId: id, taskId: id });
      }
    });

    proc.on('close', (code) => {
      outputStream.close();
      agentsRef.current.delete(id);
      setAgents(new Map(agentsRef.current));

      if (code === 0) {
        addLog({ type: 'system', message: `Agent ${id.slice(0, 8)} completed`, taskId: id });
      } else {
        addLog({ type: 'error', message: `Agent ${id.slice(0, 8)} failed (exit ${code})`, taskId: id });
      }
    });

    proc.on('error', (error) => {
      outputStream.close();
      agentsRef.current.delete(id);
      setAgents(new Map(agentsRef.current));
      addLog({ type: 'error', message: `Failed to start fallback agent: ${error.message}`, taskId: id });
    });

    const agent: FallbackAgent = {
      id,
      process: proc,
      description,
      startedAt: new Date(),
    };

    agentsRef.current.set(id, agent);
    setAgents(new Map(agentsRef.current));
  }, [cwd, addLog]);

  const stopFallbackAgents = useCallback(() => {
    if (agentsRef.current.size === 0) {
      return false;
    }

    for (const agent of agentsRef.current.values()) {
      try {
        if (agent.process.pid) {
          process.kill(-agent.process.pid, 'SIGTERM');
        } else {
          agent.process.kill('SIGTERM');
        }
      } catch {
        try {
          agent.process.kill('SIGTERM');
        } catch {
          // ignore
        }
      }
    }

    agentsRef.current.clear();
    setAgents(new Map());
    addLog({ type: 'system', message: 'Stopping fallback agents...' });
    return true;
  }, [addLog]);

  const spawn = useCallback((id: string, description: string) => {
    if (modeRef.current === 'fallback') {
      spawnFallbackAgent(id, description);
      return;
    }

    startDaemon();
    if (modeRef.current === 'fallback') {
      spawnFallbackAgent(id, description);
    }
  }, [startDaemon, spawnFallbackAgent]);

  const kill = useCallback((id: string) => {
    const fallbackAgent = agentsRef.current.get(id);
    if (fallbackAgent) {
      try {
        process.kill(-fallbackAgent.process.pid!, 'SIGTERM');
      } catch {
        fallbackAgent.process.kill('SIGTERM');
      }
      agentsRef.current.delete(id);
      setAgents(new Map(agentsRef.current));
      addLog({ type: 'system', message: `Fallback agent ${id.slice(0, 8)} terminated`, taskId: id });
      return;
    }

    const proc = spawnProcess('adw', ['cancel', '--yes', id], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    proc.stdout?.on('data', (data: Buffer) => {
      const text = stripAnsi(data.toString()).trim();
      if (text) {
        addLog({ type: 'system', message: text, taskId: id });
      }
    });

    proc.stderr?.on('data', (data: Buffer) => {
      const text = stripAnsi(data.toString()).trim();
      if (text) {
        addLog({ type: 'error', message: text, taskId: id });
      }
    });

    proc.on('error', (error) => {
      addLog({ type: 'error', message: `Failed to cancel task: ${error.message}`, taskId: id });
    });
  }, [cwd, addLog]);

  const poll = useCallback(() => {
    return [] as string[];
  }, []);

  return { daemonRunning, agentMode, agents, spawn, kill, poll, stopDaemon, stopFallbackAgents };
}

function handleClaudeEvent(
  agentId: string,
  event: any,
  addLog: (entry: Omit<LogEntry, 'timestamp'>) => void
) {
  const type = event.type;

  if (type === 'assistant') {
    const content = event.message?.content;
    if (Array.isArray(content)) {
      for (const c of content) {
        if (c.type === 'text' && c.text) {
          const text = c.text.slice(0, 80);
          addLog({ type: 'agent', message: text, agentId, taskId: agentId });
          break;
        }
      }
    }
  } else if (type === 'tool_use') {
    const tool = event.tool?.name || 'unknown';
    addLog({ type: 'tool', message: `Using ${tool}`, agentId, taskId: agentId });
  } else if (type === 'result') {
    addLog({ type: 'system', message: `Agent ${agentId.slice(0, 8)} finished`, agentId, taskId: agentId });
  } else if (type === 'error') {
    const msg = event.error?.message || 'Unknown error';
    addLog({ type: 'error', message: msg, agentId, taskId: agentId });
  }
}

export const __test__ = {
  parseEventData,
  formatEventMessage,
  eventLogType,
};
