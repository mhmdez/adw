import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface ClaudeContext {
  task?: { id?: string; description?: string; tags?: string[] };
  subtask?: string;
  attachments?: { path: string; content: string }[];
  recentLogs?: string[];
}

export async function askClaude(question: string, cwd: string, context?: ClaudeContext): Promise<string> {
  return new Promise((resolve, reject) => {
    // Build prompt with context if available
    let contextText = '';
    const claudeMd = join(cwd, 'CLAUDE.md');
    if (existsSync(claudeMd)) {
      try {
        const content = readFileSync(claudeMd, 'utf-8');
        contextText = `Project context:\n${content.slice(0, 2000)}\n\n`;
      } catch {
        // Ignore
      }
    }

    if (context?.task) {
      const tags = context.task.tags?.length ? ` (${context.task.tags.join(', ')})` : '';
      contextText += `Task: ${context.task.description ?? 'Unknown'}${tags}\n`;
      if (context.task.id) {
        contextText += `Task ID: ${context.task.id}\n`;
      }
      if (context.subtask) {
        contextText += `Subtask: ${context.subtask}\n`;
      }
      contextText += '\n';
    }

    if (context?.attachments && context.attachments.length > 0) {
      contextText += 'Attached files:\n';
      for (const file of context.attachments) {
        contextText += `--- ${file.path} ---\n${file.content}\n\n`;
      }
    }

    if (context?.recentLogs && context.recentLogs.length > 0) {
      contextText += 'Recent updates:\n';
      for (const line of context.recentLogs) {
        contextText += `- ${line}\n`;
      }
      contextText += '\n';
    }

    const prompt = `${contextText}Question: ${question}

Provide a concise, helpful answer.`;

    const proc = spawn('claude', ['--print', prompt], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    proc.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString();
    });

    proc.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(new Error(stderr || `Exit code ${code}`));
      }
    });

    proc.on('error', (err) => {
      reject(err);
    });

    // Timeout after 2 minutes
    setTimeout(() => {
      proc.kill();
      reject(new Error('Timeout'));
    }, 120000);
  });
}
