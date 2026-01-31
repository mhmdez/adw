import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

export async function askClaude(question: string, cwd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    // Build prompt with context if available
    let context = '';
    const claudeMd = join(cwd, 'CLAUDE.md');
    if (existsSync(claudeMd)) {
      try {
        const content = readFileSync(claudeMd, 'utf-8');
        context = `Project context:\n${content.slice(0, 2000)}\n\n`;
      } catch {
        // Ignore
      }
    }

    const prompt = `${context}Question: ${question}

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
