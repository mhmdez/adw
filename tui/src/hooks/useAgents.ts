import { useState, useCallback, useRef } from 'react';
import { spawn as spawnProcess, ChildProcess } from 'child_process';
import { join } from 'path';
import { mkdirSync, existsSync, createWriteStream } from 'fs';
import { LogEntry } from './useLogs.js';

interface Agent {
  id: string;
  process: ChildProcess;
  description: string;
  startedAt: Date;
}

export function useAgents(cwd: string, addLog: (entry: Omit<LogEntry, 'timestamp'>) => void) {
  const agentsRef = useRef<Map<string, Agent>>(new Map());
  const [agents, setAgents] = useState<Map<string, Agent>>(new Map());

  const spawn = useCallback((id: string, description: string) => {
    // Create agents directory
    const agentDir = join(cwd, 'agents', id, 'prompt');
    if (!existsSync(agentDir)) {
      mkdirSync(agentDir, { recursive: true });
    }

    const outputFile = join(agentDir, 'cc_raw_output.jsonl');
    const outputStream = createWriteStream(outputFile);

    const prompt = `Task ID: ${id}

Please complete this task:

${description}

Work in the current directory. When done, summarize what you accomplished.`;

    const proc = spawnProcess('claude', [
      '--model', 'sonnet',
      '--output-format', 'stream-json',
      '--print', prompt,
    ], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
    });

    // Pipe stdout to file and parse for logs
    proc.stdout?.on('data', (data: Buffer) => {
      outputStream.write(data);

      // Try to parse JSONL for live updates
      const lines = data.toString().split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const event = JSON.parse(line);
          handleAgentEvent(id, event, addLog);
        } catch {
          // Ignore parse errors
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

    const agent: Agent = {
      id,
      process: proc,
      description,
      startedAt: new Date(),
    };

    agentsRef.current.set(id, agent);
    setAgents(new Map(agentsRef.current));
  }, [cwd, addLog]);

  const kill = useCallback((id: string) => {
    const agent = agentsRef.current.get(id);
    if (agent) {
      try {
        process.kill(-agent.process.pid!, 'SIGTERM');
      } catch {
        agent.process.kill('SIGTERM');
      }
      agentsRef.current.delete(id);
      setAgents(new Map(agentsRef.current));
    }
  }, []);

  const poll = useCallback(() => {
    // Poll is handled by process events, this just returns completed
    return [];
  }, []);

  return { agents, spawn, kill, poll };
}

function handleAgentEvent(
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
