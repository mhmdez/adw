import React, { useState, useEffect, useCallback } from 'react';
import { Box, Text, useInput, useApp } from 'ink';
import TextInput from 'ink-text-input';
import Spinner from 'ink-spinner';
import { TaskList } from './components/TaskList.js';
import { LogView } from './components/LogView.js';
import { useTasks, Task } from './hooks/useTasks.js';
import { useAgents } from './hooks/useAgents.js';
import { useLogs, LogEntry } from './hooks/useLogs.js';
import { askClaude } from './utils/claude.js';

interface AppProps {
  cwd: string;
}

export function App({ cwd }: AppProps) {
  const { exit } = useApp();
  const [input, setInput] = useState('');
  const [logs, addLog] = useLogs();
  const { tasks, reload: reloadTasks, addTask, updateTask } = useTasks(cwd);
  const { agents, spawn, kill, poll } = useAgents(cwd, addLog);
  const [isThinking, setIsThinking] = useState(false);

  // Poll agents periodically
  useEffect(() => {
    const interval = setInterval(() => {
      const completed = poll();
      if (completed.length > 0) {
        reloadTasks();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [poll, reloadTasks]);

  // Handle keyboard shortcuts
  useInput((input, key) => {
    if (key.ctrl && input === 'c') {
      exit();
    }
  });

  const handleSubmit = useCallback(async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    setInput('');

    // Handle commands
    if (trimmed.startsWith('/')) {
      await handleCommand(trimmed);
      return;
    }

    // Detect question vs task
    const questionStarters = ['what', 'how', 'why', 'where', 'when', 'who', 'which', 'can', 'could', 'would', 'is', 'are', 'do', 'does', 'explain', 'describe', 'tell', 'show'];
    const isQuestion = trimmed.endsWith('?') || questionStarters.some(s => trimmed.toLowerCase().startsWith(s));

    if (isQuestion) {
      await handleQuestion(trimmed);
    } else {
      await handleNewTask(trimmed);
    }
  }, []);

  const handleCommand = async (cmd: string) => {
    const parts = cmd.slice(1).split(/\s+/);
    const command = parts[0]?.toLowerCase();
    const args = parts.slice(1).join(' ');

    switch (command) {
      case 'help':
        showHelp();
        break;
      case 'new':
      case 'do':
      case 'task':
        if (args) {
          await handleNewTask(args);
        } else {
          addLog({ type: 'error', message: 'Usage: /new <task description>' });
        }
        break;
      case 'ask':
        if (args) {
          await handleQuestion(args);
        } else {
          addLog({ type: 'error', message: 'Usage: /ask <question>' });
        }
        break;
      case 'tasks':
      case 'list':
        reloadTasks();
        addLog({ type: 'system', message: `Loaded ${tasks.length} tasks` });
        break;
      case 'kill':
        if (args) {
          kill(args);
          addLog({ type: 'system', message: `Killed agent ${args.slice(0, 8)}` });
        } else {
          addLog({ type: 'error', message: 'Usage: /kill <agent_id>' });
        }
        break;
      case 'status':
        showStatus();
        break;
      case 'clear':
        // Clear is handled by the logs hook
        break;
      case 'quit':
      case 'exit':
        exit();
        break;
      default:
        addLog({ type: 'error', message: `Unknown command: /${command}` });
        addLog({ type: 'system', message: 'Type /help for available commands' });
    }
  };

  const handleQuestion = async (question: string) => {
    addLog({ type: 'user', message: question });
    setIsThinking(true);

    try {
      const response = await askClaude(question, cwd);
      addLog({ type: 'assistant', message: response });
    } catch (error) {
      addLog({ type: 'error', message: `Failed to get response: ${error}` });
    } finally {
      setIsThinking(false);
    }
  };

  const handleNewTask = async (description: string) => {
    addLog({ type: 'user', message: description });
    addLog({ type: 'system', message: 'Creating task...' });

    const task = addTask(description);
    addLog({ type: 'system', message: `Task ${task.id.slice(0, 8)} created` });

    try {
      spawn(task.id, description);
      addLog({ type: 'system', message: `Agent spawned for ${task.id.slice(0, 8)}` });
    } catch (error) {
      addLog({ type: 'error', message: `Failed to spawn agent: ${error}` });
    }
  };

  const showHelp = () => {
    const help = [
      '',
      'Commands:',
      '  /new <desc>     Create and run a task',
      '  /ask <question> Ask Claude a question',
      '  /tasks          Refresh task list',
      '  /kill <id>      Kill running agent',
      '  /status         Show status',
      '  /clear          Clear logs',
      '  /quit           Exit',
      '',
      'Or just type:',
      '  Questions (ending with ?) get answered',
      '  Everything else becomes a task',
      '',
    ];
    help.forEach(line => addLog({ type: 'system', message: line }));
  };

  const showStatus = () => {
    const running = tasks.filter(t => t.status === 'in_progress').length;
    const pending = tasks.filter(t => t.status === 'pending').length;
    const done = tasks.filter(t => t.status === 'done').length;

    addLog({ type: 'system', message: '' });
    addLog({ type: 'system', message: `Tasks: ${tasks.length} total` });
    addLog({ type: 'system', message: `  Running: ${running}` });
    addLog({ type: 'system', message: `  Pending: ${pending}` });
    addLog({ type: 'system', message: `  Done: ${done}` });
    addLog({ type: 'system', message: `Agents: ${agents.size} active` });
    addLog({ type: 'system', message: '' });
  };

  const runningCount = tasks.filter(t => t.status === 'in_progress').length;

  return (
    <Box flexDirection="column" height="100%">
      {/* Header with ASCII Logo */}
      <Box flexDirection="column">
        <Text color="cyan" bold>
          {`█████╗ ██████╗ ██╗    ██╗`}
        </Text>
        <Text color="cyan" bold>
          {`██╔══██╗██╔══██╗██║    ██║`}
        </Text>
        <Text color="cyan" bold>
          {`███████║██║  ██║██║ █╗ ██║`}
        </Text>
        <Text color="cyan" bold>
          {`██╔══██║██║  ██║██║███╗██║`}
        </Text>
        <Text color="cyan" bold>
          {`██║  ██║██████╔╝╚███╔███╔╝`}
        </Text>
        <Text color="cyan" bold>
          {`╚═╝  ╚═╝╚═════╝  ╚══╝╚══╝`}
        </Text>
        <Box marginTop={1}>
          <Text color="magenta" bold>✨ AI Developer Workflow</Text>
          <Text dimColor> — Ship features while you sleep</Text>
        </Box>
        <Box>
          <Text dimColor>by </Text>
          <Text color="blue">mhmdez@me.com</Text>
        </Box>
      </Box>

      {/* Separator */}
      <Box marginTop={1}>
        <Text dimColor>{'─'.repeat(50)}</Text>
      </Box>

      {/* Tasks */}
      {tasks.length > 0 && (
        <Box flexDirection="column" marginTop={1}>
          <Text color="cyan" bold>📋 TASKS</Text>
          <TaskList tasks={tasks} maxItems={5} />
        </Box>
      )}

      {/* Logs */}
      <Box flexDirection="column" flexGrow={1} marginTop={1}>
        <LogView logs={logs} />
      </Box>

      {/* Separator */}
      <Box>
        <Text dimColor>{'─'.repeat(50)}</Text>
      </Box>

      {/* Input */}
      <Box marginTop={1}>
        {isThinking ? (
          <Box>
            <Text color="cyan">
              <Spinner type="dots" />
            </Text>
            <Text color="yellow"> Thinking...</Text>
          </Box>
        ) : (
          <Box>
            <Text color="cyan" bold>❯ </Text>
            <TextInput
              value={input}
              onChange={setInput}
              onSubmit={handleSubmit}
              placeholder="Type /help for commands"
            />
            {runningCount > 0 && (
              <Text color="green"> ⚡ {runningCount} running</Text>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
