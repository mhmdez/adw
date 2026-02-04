import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Box, Text, useInput, useApp } from 'ink';
import TextInput from 'ink-text-input';
import Spinner from 'ink-spinner';
import { spawn as spawnProcess, ChildProcess } from 'child_process';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { TaskList } from './components/TaskList.js';
import { LogView } from './components/LogView.js';
import { useTasks, Task, Subtask } from './hooks/useTasks.js';
import { useAgents } from './hooks/useAgents.js';
import { useLogs } from './hooks/useLogs.js';
import { useFileIndex } from './hooks/useFileIndex.js';
import { useGitStatus } from './hooks/useGitStatus.js';
import { askClaude } from './utils/claude.js';

interface AppProps {
  cwd: string;
}

type SuggestionType = 'command' | 'action' | 'file' | 'tag';

interface Suggestion {
  type: SuggestionType;
  value: string;
  description?: string;
}

interface TestStatus {
  status: 'idle' | 'running' | 'passed' | 'failed' | 'error';
  lastRun?: Date;
  command?: string;
  summary?: string;
}

const COMMANDS: Suggestion[] = [
  { type: 'command', value: 'new', description: 'Create a task' },
  { type: 'command', value: 'ask', description: 'Ask a question' },
  { type: 'command', value: 'tasks', description: 'Refresh task list' },
  { type: 'command', value: 'plan', description: 'Show plan steps' },
  { type: 'command', value: 'pause', description: 'Pause task' },
  { type: 'command', value: 'resume', description: 'Resume task' },
  { type: 'command', value: 'approve', description: 'Approve task' },
  { type: 'command', value: 'summarize', description: 'Summarize progress' },
  { type: 'command', value: 'test', description: 'Run tests' },
  { type: 'command', value: 'files', description: 'Show changed files' },
  { type: 'command', value: 'tags', description: 'Show task tags' },
  { type: 'command', value: 'status', description: 'Show status' },
  { type: 'command', value: 'kill', description: 'Kill agent' },
  { type: 'command', value: 'quit', description: 'Exit' },
];

const ACTIONS: Suggestion[] = [
  { type: 'action', value: 'resume', description: 'Resume task' },
  { type: 'action', value: 'pause', description: 'Pause task' },
  { type: 'action', value: 'rerun-tests', description: 'Rerun tests' },
  { type: 'action', value: 'open-logs', description: 'Open agent logs' },
];

const TAG_OPTIONS = [
  'bug',
  'feature',
  'chore',
  'p0',
  'p1',
  'p2',
  'p3',
  'owner:me',
  'priority:high',
  'priority:medium',
  'priority:low',
];

export function App({ cwd }: AppProps) {
  const { exit } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [logs, addLog] = useLogs();
  const { tasks, reload: reloadTasks, addTask, setTaskStatus, setTaskTags } = useTasks(cwd);
  const { agents, spawn, kill, poll } = useAgents(cwd, addLog);
  const { files: indexedFiles, isIndexing } = useFileIndex(cwd);
  const { files: changedFiles, isRepo } = useGitStatus(cwd);
  const [isThinking, setIsThinking] = useState(false);
  const [showInbox, setShowInbox] = useState(true);
  const [showContext, setShowContext] = useState(true);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [pendingSelectTaskId, setPendingSelectTaskId] = useState<string | null>(null);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);
  const [testCommand, setTestCommand] = useState<string | null>(null);
  const [testStatusByTask, setTestStatusByTask] = useState<Record<string, TestStatus>>({});
  const [attachedFilesByTask, setAttachedFilesByTask] = useState<Record<string, string[]>>({});
  const testProcessRef = useRef<ChildProcess | null>(null);

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

  const normalizeToken = (token: string) => token.replace(/^[#@]/, '').replace(/[.,;:]+$/, '');

  const extractTokens = (value: string) => {
    const parts = value.split(/\s+/).filter(Boolean);
    const tags = parts.filter(part => part.startsWith('#')).map(normalizeToken);
    const files = parts.filter(part => part.startsWith('@')).map(normalizeToken);
    const cleaned = parts.filter(part => !part.startsWith('#') && !part.startsWith('@')).join(' ');
    return { cleaned, tags, files };
  };

  const mergeTags = (existing: string[] | undefined, incoming: string[]) => {
    const set = new Set<string>([...(existing ?? []), ...incoming].map(tag => tag.trim()).filter(Boolean));
    return Array.from(set);
  };

  const detectTestCommand = () => {
    const packageJson = join(cwd, 'package.json');
    if (existsSync(packageJson)) {
      return 'npm test';
    }
    const pyproject = join(cwd, 'pyproject.toml');
    const uvLock = join(cwd, 'uv.lock');
    if (existsSync(pyproject) || existsSync(uvLock)) {
      return 'uv run pytest tests/ -v';
    }
    const cargo = join(cwd, 'Cargo.toml');
    if (existsSync(cargo)) {
      return 'cargo test';
    }
    return null;
  };

  const updateTestStatus = (taskId: string, next: Partial<TestStatus>) => {
    setTestStatusByTask(prev => ({
      ...prev,
      [taskId]: {
        status: 'idle',
        ...prev[taskId],
        ...next,
      },
    }));
  };

  const toggleFocus = () => {
    if (showInbox || showContext) {
      setShowInbox(false);
      setShowContext(false);
    } else {
      setShowInbox(true);
      setShowContext(true);
    }
  };

  const runTests = (taskId: string, overrideCommand?: string) => {
    if (testProcessRef.current) {
      addLog({ type: 'error', message: 'Tests are already running.', taskId });
      return;
    }
    const command = overrideCommand || testCommand || detectTestCommand();
    if (!command) {
      addLog({ type: 'error', message: 'No test command detected. Use /test <command>.', taskId });
      return;
    }

    setTestCommand(command);
    updateTestStatus(taskId, { status: 'running', lastRun: new Date(), command });
    addLog({ type: 'system', message: `Running tests: ${command}`, taskId });

    const proc = spawnProcess(command, { cwd, shell: true });
    testProcessRef.current = proc;
    let output = '';

    proc.stdout?.on('data', (data: Buffer) => {
      output += data.toString();
    });
    proc.stderr?.on('data', (data: Buffer) => {
      output += data.toString();
    });

    proc.on('close', (code) => {
      testProcessRef.current = null;
      const lines = output.trim().split('\n').slice(-6).join('\n');
      if (code === 0) {
        updateTestStatus(taskId, { status: 'passed', summary: lines });
        addLog({ type: 'system', message: 'Tests passed ✅', taskId });
      } else {
        updateTestStatus(taskId, { status: 'failed', summary: lines });
        addLog({ type: 'error', message: 'Tests failed ❌', taskId });
      }
      if (lines) {
        addLog({ type: 'system', message: lines, taskId });
      }
    });

    proc.on('error', (error) => {
      testProcessRef.current = null;
      updateTestStatus(taskId, { status: 'error', summary: String(error) });
      addLog({ type: 'error', message: `Failed to run tests: ${error}`, taskId });
    });
  };

  const handleSubmit = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    setInputValue('');

    // Handle commands
    if (trimmed.startsWith('/')) {
      await handleCommand(trimmed);
      return;
    }

    if (trimmed.startsWith('>')) {
      await handleQuickAction(trimmed);
      return;
    }

    if (trimmed.startsWith('#') && selectedTaskId) {
      await handleTagInput(trimmed);
      return;
    }

    if (selectedItem?.type === 'task' || selectedItem?.type === 'subtask') {
      await handleQuestion(trimmed);
      return;
    }

    const questionStarters = ['what', 'how', 'why', 'where', 'when', 'who', 'which', 'can', 'could', 'would', 'is', 'are', 'do', 'does', 'explain', 'describe', 'tell', 'show'];
    const isQuestion = trimmed.endsWith('?') || questionStarters.some(s => trimmed.toLowerCase().startsWith(s));

    if (isQuestion) {
      await handleQuestion(trimmed);
    } else {
      await handleNewTask(trimmed);
    }
  };

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
      case 'plan':
        showPlan();
        break;
      case 'pause':
        pauseTask();
        break;
      case 'resume':
        resumeTask();
        break;
      case 'approve':
        approveTask();
        break;
      case 'summarize':
        await summarizeTask();
        break;
      case 'test':
        if (selectedTaskId) {
          runTests(selectedTaskId, args || undefined);
        } else {
          addLog({ type: 'error', message: 'Select a task to run tests.' });
        }
        break;
      case 'files':
        showFiles();
        break;
      case 'tags':
        showTags();
        break;
      case 'focus':
        toggleFocus();
        break;
      case 'inbox':
        setShowInbox(prev => !prev);
        break;
      case 'context':
        setShowContext(prev => !prev);
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
    const { cleaned, tags, files } = extractTokens(question);
    const taskId = selectedTaskId;
    const subtaskId = selectedSubtaskId;
    addLog({ type: 'user', message: question, taskId, subtaskId });

    if (taskId && tags.length > 0) {
      const existingTags = selectedTask?.tags ?? [];
      const merged = mergeTags(existingTags, tags);
      setTaskTags(taskId, merged);
    }

    const attachments = files
      .map(file => {
        const fullPath = file.startsWith('/') ? file : join(cwd, file);
        if (!existsSync(fullPath)) {
          addLog({ type: 'error', message: `File not found: ${file}`, taskId, subtaskId });
          return null;
        }
        const content = readFileSync(fullPath, 'utf-8').slice(0, 2000);
        return { path: file, content };
      })
      .filter((item): item is { path: string; content: string } => Boolean(item));

    if (taskId && attachments.length > 0) {
      setAttachedFilesByTask(prev => ({
        ...prev,
        [taskId]: Array.from(new Set([...(prev[taskId] ?? []), ...attachments.map(a => a.path)])),
      }));
    }

    const questionText = cleaned || (attachments.length > 0 ? 'Review the attached files.' : question);
    setIsThinking(true);

    try {
      const response = await askClaude(questionText, cwd, {
        task: selectedTask ? { id: selectedTask.id, description: selectedTask.description, tags: selectedTask.tags } : undefined,
        subtask: selectedSubtask?.title,
        attachments,
        recentLogs: filteredLogs.slice(-12).map(log => log.message),
      });
      addLog({ type: 'assistant', message: response, taskId, subtaskId });
    } catch (error) {
      addLog({ type: 'error', message: `Failed to get response: ${error}`, taskId, subtaskId });
    } finally {
      setIsThinking(false);
    }
  };

  const handleNewTask = async (description: string) => {
    const { cleaned, tags, files } = extractTokens(description);
    const taskDescription = cleaned || description;
    const task = addTask(taskDescription, tags);
    addLog({ type: 'user', message: description, taskId: task.id });
    addLog({ type: 'system', message: 'Creating task...', taskId: task.id });
    addLog({ type: 'system', message: `Task ${task.id.slice(0, 8)} created`, taskId: task.id });
    setPendingSelectTaskId(task.id);

    if (files.length > 0) {
      setAttachedFilesByTask(prev => ({
        ...prev,
        [task.id]: Array.from(new Set([...(prev[task.id] ?? []), ...files])),
      }));
    }

    try {
      spawn(task.id, taskDescription);
      addLog({ type: 'system', message: `Agent spawned for ${task.id.slice(0, 8)}`, taskId: task.id });
    } catch (error) {
      addLog({ type: 'error', message: `Failed to spawn agent: ${error}`, taskId: task.id });
    }
  };

  const showPlan = () => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to view its plan.' });
      return;
    }
    const steps = selectedTask.subtasks ?? [];
    if (steps.length === 0) {
      addLog({ type: 'system', message: 'No plan steps found for this task.', taskId: selectedTask.id });
      return;
    }
    addLog({ type: 'system', message: 'Plan steps:', taskId: selectedTask.id });
    steps.forEach(step => {
      const checkbox = step.status === 'done' ? '[x]' : '[ ]';
      addLog({ type: 'system', message: `${checkbox} ${step.title}`, taskId: selectedTask.id, subtaskId: step.id });
    });
  };

  const pauseTask = () => {
    if (!selectedTaskId) {
      addLog({ type: 'error', message: 'Select a task to pause.' });
      return;
    }
    setTaskStatus(selectedTaskId, 'blocked');
    addLog({ type: 'system', message: 'Task paused.', taskId: selectedTaskId });
  };

  const resumeTask = () => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to resume.' });
      return;
    }
    setTaskStatus(selectedTask.id, 'in_progress');
    if (agents.has(selectedTask.id)) {
      addLog({ type: 'system', message: 'Agent already running for this task.', taskId: selectedTask.id });
      return;
    }
    spawn(selectedTask.id, selectedTask.description);
    addLog({ type: 'system', message: 'Task resumed.', taskId: selectedTask.id });
  };

  const approveTask = () => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to approve.' });
      return;
    }
    const merged = mergeTags(selectedTask.tags, ['approved']);
    setTaskTags(selectedTask.id, merged);
    addLog({ type: 'system', message: 'Task approved ✅', taskId: selectedTask.id });
  };

  const summarizeTask = async () => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to summarize.' });
      return;
    }
    const recent = logs.filter(log => log.taskId === selectedTask.id).slice(-20).map(log => log.message);
    if (recent.length === 0) {
      addLog({ type: 'system', message: 'No activity to summarize yet.', taskId: selectedTask.id });
      return;
    }
    addLog({ type: 'system', message: 'Summarizing progress...', taskId: selectedTask.id });
    try {
      const response = await askClaude(
        `Summarize the current progress for task "${selectedTask.description}".`,
        cwd,
        { recentLogs: recent },
      );
      addLog({ type: 'assistant', message: response, taskId: selectedTask.id });
    } catch (error) {
      addLog({ type: 'error', message: `Failed to summarize: ${error}`, taskId: selectedTask.id });
    }
  };

  const showFiles = () => {
    if (!isRepo) {
      addLog({ type: 'error', message: 'Not in a git repository.' });
      return;
    }
    if (changedFiles.length === 0) {
      addLog({ type: 'system', message: 'No changed files detected.' });
      return;
    }
    addLog({ type: 'system', message: 'Changed files:' });
    changedFiles.slice(0, 12).forEach(file => {
      addLog({ type: 'system', message: `- ${file}` });
    });
  };

  const showTags = () => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to view tags.' });
      return;
    }
    const tags = selectedTask.tags ?? [];
    addLog({ type: 'system', message: tags.length ? `Tags: ${tags.join(', ')}` : 'No tags yet.', taskId: selectedTask.id });
  };

  const handleTagInput = async (value: string) => {
    if (!selectedTask) {
      addLog({ type: 'error', message: 'Select a task to tag.' });
      return;
    }
    const { tags } = extractTokens(value);
    if (tags.length === 0) {
      addLog({ type: 'error', message: 'No tags detected. Use #tag.' });
      return;
    }
    const merged = mergeTags(selectedTask.tags, tags);
    setTaskTags(selectedTask.id, merged);
    addLog({ type: 'system', message: `Tags updated: ${merged.join(', ')}`, taskId: selectedTask.id });
  };

  const handleQuickAction = async (value: string) => {
    const action = value.slice(1).trim().split(/\s+/)[0]?.toLowerCase();
    if (!action) {
      addLog({ type: 'error', message: 'Usage: > <resume|pause|rerun-tests|open-logs>' });
      return;
    }
    switch (action) {
      case 'resume':
        resumeTask();
        break;
      case 'pause':
        pauseTask();
        break;
      case 'rerun-tests':
      case 'tests':
        if (selectedTaskId) {
          runTests(selectedTaskId);
        } else {
          addLog({ type: 'error', message: 'Select a task to run tests.' });
        }
        break;
      case 'open-logs':
      case 'logs':
        if (!selectedTaskId) {
          addLog({ type: 'error', message: 'Select a task to open logs.' });
          break;
        }
        const logPath = join(cwd, 'agents', selectedTaskId, 'prompt', 'cc_raw_output.jsonl');
        if (existsSync(logPath)) {
          addLog({ type: 'system', message: `Agent log: ${logPath}`, taskId: selectedTaskId });
        } else {
          addLog({ type: 'error', message: 'Agent log not found yet.', taskId: selectedTaskId });
        }
        break;
      default:
        addLog({ type: 'error', message: `Unknown action: ${action}` });
    }
  };

  const showHelp = () => {
    const help = [
      '',
      'Commands:',
      '  /new <desc>     Create and run a task',
      '  /ask <question> Ask Claude a question',
      '  /tasks          Refresh task list',
      '  /plan           Show plan steps',
      '  /pause          Pause selected task',
      '  /resume         Resume selected task',
      '  /approve        Approve selected task',
      '  /summarize      Summarize selected task',
      '  /test [cmd]     Run tests (optional command)',
      '  /files          Show changed files',
      '  /tags           Show task tags',
      '  /kill <id>      Kill running agent',
      '  /status         Show status',
      '  /clear          Clear logs',
      '  /quit           Exit',
      '',
      'Or just type:',
      '  Questions (ending with ?) get answered',
      '  Everything else becomes a task',
      '',
      'Quick actions:',
      '  > resume | pause | rerun-tests | open-logs',
      '',
    ];
    help.forEach(line => addLog({ type: 'system', message: line }));
  };

  const showStatus = () => {
    const running = tasks.filter(t => t.status === 'in_progress').length;
    const pending = tasks.filter(t => t.status === 'pending').length;
    const done = tasks.filter(t => t.status === 'done').length;
    const blocked = tasks.filter(t => t.status === 'blocked').length;
    const failed = tasks.filter(t => t.status === 'failed').length;

    addLog({ type: 'system', message: '' });
    addLog({ type: 'system', message: `Tasks: ${tasks.length} total` });
    addLog({ type: 'system', message: `  Running: ${running}` });
    addLog({ type: 'system', message: `  Pending: ${pending}` });
    addLog({ type: 'system', message: `  Blocked: ${blocked}` });
    addLog({ type: 'system', message: `  Failed: ${failed}` });
    addLog({ type: 'system', message: `  Done: ${done}` });
    addLog({ type: 'system', message: `Agents: ${agents.size} active` });
    addLog({ type: 'system', message: '' });
  };

  const runningCount = tasks.filter(t => t.status === 'in_progress').length;
  const pendingCount = tasks.filter(t => t.status === 'pending').length;
  const blockedCount = tasks.filter(t => t.status === 'blocked').length;
  const failedCount = tasks.filter(t => t.status === 'failed').length;
  const doneCount = tasks.filter(t => t.status === 'done').length;
  const safetyEnabled = useMemo(() => existsSync(join(cwd, '.claude', 'hooks')), [cwd]);

  const sortedTasks = useMemo(() => {
    const order: Record<string, number> = {
      'in_progress': 0,
      'pending': 1,
      'blocked': 2,
      'failed': 3,
      'done': 4,
    };
    return [...tasks].sort((a, b) => (order[a.status] ?? 5) - (order[b.status] ?? 5));
  }, [tasks]);

  type InboxItem =
    | { type: 'task'; task: Task }
    | { type: 'subtask'; task: Task; subtask: Subtask }
    | { type: 'new' };

  const inboxItems: InboxItem[] = useMemo(() => {
    const items: InboxItem[] = [];
    for (const task of sortedTasks) {
      items.push({ type: 'task', task });
      if (expandedTasks.has(task.id)) {
        for (const subtask of task.subtasks ?? []) {
          items.push({ type: 'subtask', task, subtask });
        }
      }
    }
    items.push({ type: 'new' });
    return items;
  }, [sortedTasks, expandedTasks]);

  useEffect(() => {
    if (selectedIndex > inboxItems.length - 1) {
      setSelectedIndex(Math.max(0, inboxItems.length - 1));
    }
  }, [inboxItems.length, selectedIndex]);

  useEffect(() => {
    if (!pendingSelectTaskId) return;
    const index = inboxItems.findIndex(item =>
      item.type === 'task' && item.task.id === pendingSelectTaskId
    );
    if (index >= 0) {
      setSelectedIndex(index);
      setPendingSelectTaskId(null);
    }
  }, [pendingSelectTaskId, inboxItems]);

  const selectedItem = inboxItems[selectedIndex];
  const selectedTask = selectedItem?.type === 'task'
    ? selectedItem.task
    : selectedItem?.type === 'subtask'
      ? selectedItem.task
      : undefined;
  const selectedSubtask = selectedItem?.type === 'subtask'
    ? selectedItem.subtask
    : undefined;
  const selectedTaskId = selectedItem?.type === 'task'
    ? selectedItem.task.id
    : selectedItem?.type === 'subtask'
      ? selectedItem.task.id
      : undefined;
  const selectedSubtaskId = selectedItem?.type === 'subtask'
    ? selectedItem.subtask.id
    : undefined;
  const selectedIsNew = selectedItem?.type === 'new';

  const planTotal = selectedTask?.subtasks?.length ?? 0;
  const planDone = selectedTask?.subtasks?.filter(step => step.status === 'done').length ?? 0;
  const selectedTest = selectedTaskId ? testStatusByTask[selectedTaskId] : undefined;
  const selectedAttachments = selectedTaskId ? (attachedFilesByTask[selectedTaskId] ?? []) : [];

  const contextSummary = selectedTask
    ? `Task ${selectedTask.id} • ${selectedTask.description} • ${selectedTask.status.replace('_', ' ')} • Plan ${planTotal ? `${planDone}/${planTotal}` : '—'} • Tests ${selectedTest?.status ?? '—'}${selectedSubtask ? ` • Subtask: ${selectedSubtask.title}` : ''}`
    : 'New task • Type a description to start';

  const planLine = selectedTask && planTotal > 0
    ? `Plan: ${selectedTask.subtasks?.slice(0, 3).map(step => `${step.status === 'done' ? '✓' : '○'} ${step.title}`).join(' | ')}${planTotal > 3 ? ' …' : ''}`
    : 'Plan: —';

  const filesLine = isRepo && changedFiles.length > 0
    ? `Files: ${changedFiles.slice(0, 3).join(', ')}${changedFiles.length > 3 ? ` +${changedFiles.length - 3} more` : ''}`
    : 'Files: —';

  const attachmentsLine = selectedAttachments.length > 0
    ? `Attached: ${selectedAttachments.slice(0, 3).join(', ')}${selectedAttachments.length > 3 ? ` +${selectedAttachments.length - 3} more` : ''}`
    : 'Attached: —';

  const testsLine = selectedTest
    ? `Tests: ${selectedTest.status}`
    : 'Tests: —';

  const taskIndexById = useMemo(() => {
    const map = new Map<string, number>();
    inboxItems.forEach((item, index) => {
      if (item.type === 'task') {
        map.set(item.task.id, index);
      }
    });
    return map;
  }, [inboxItems]);

  const lastActivityByTask = useMemo(() => {
    const activity: Record<string, string> = {};
    for (let i = logs.length - 1; i >= 0; i -= 1) {
      const log = logs[i];
      if (log.taskId && !activity[log.taskId]) {
        activity[log.taskId] = log.message;
      }
    }
    return activity;
  }, [logs]);

  const subtitleByTask = useMemo(() => {
    const result: Record<string, string> = {};
    for (const task of sortedTasks) {
      const parts: string[] = [];
      const total = task.subtasks?.length ?? 0;
      if (total > 0) {
        const done = task.subtasks?.filter(step => step.status === 'done').length ?? 0;
        parts.push(`Plan ${done}/${total}`);
      }
      if (task.tags && task.tags.length > 0) {
        parts.push(`Tags ${task.tags.join(', ')}`);
      }
      const testStatus = testStatusByTask[task.id]?.status;
      if (testStatus) {
        parts.push(`Tests ${testStatus}`);
      }
      if (lastActivityByTask[task.id]) {
        parts.push(lastActivityByTask[task.id]);
      }
      if (parts.length > 0) {
        result[task.id] = parts.join(' • ');
      }
    }
    return result;
  }, [sortedTasks, testStatusByTask, lastActivityByTask]);

  const filteredLogs = useMemo(() => {
    if (selectedTaskId) {
      return logs.filter(log =>
        log.taskId === selectedTaskId && (selectedSubtaskId ? log.subtaskId === selectedSubtaskId : true)
      );
    }
    return logs.filter(log => !log.taskId);
  }, [logs, selectedTaskId, selectedSubtaskId]);

  const inputHint = useMemo(() => {
    if (inputValue.startsWith('/')) {
      return 'Commands: /new /ask /tasks /status /kill /quit';
    }
    if (inputValue.startsWith('@')) {
      return 'Attach files: @path (type to filter)';
    }
    if (inputValue.startsWith('#')) {
      return 'Tags: #bug #feature #chore';
    }
    return 'Hints: / commands • > actions • @ files • # tags • Tab autocomplete • ↑↓ select • ←→ expand • i inbox • c context • f focus';
  }, [inputValue]);

  const completionContext = useMemo(() => {
    if (inputValue.startsWith('/')) {
      const spaceIndex = inputValue.indexOf(' ');
      if (spaceIndex === -1) {
        return { type: 'command' as const, query: inputValue.slice(1), replaceStart: 0 };
      }
    }
    if (inputValue.startsWith('>')) {
      const spaceIndex = inputValue.indexOf(' ');
      if (spaceIndex === -1) {
        return { type: 'action' as const, query: inputValue.slice(1), replaceStart: 0 };
      }
    }

    const fileMatch = inputValue.match(/(^|\s)@([^\s]*)$/);
    if (fileMatch && typeof fileMatch.index === 'number') {
      const replaceStart = fileMatch.index + fileMatch[1].length;
      return { type: 'file' as const, query: fileMatch[2], replaceStart };
    }

    const tagMatch = inputValue.match(/(^|\s)#([^\s]*)$/);
    if (tagMatch && typeof tagMatch.index === 'number') {
      const replaceStart = tagMatch.index + tagMatch[1].length;
      return { type: 'tag' as const, query: tagMatch[2], replaceStart };
    }

    return null;
  }, [inputValue]);

  const suggestions = useMemo(() => {
    if (!completionContext) return [];
    const query = completionContext.query.toLowerCase();
    if (completionContext.type === 'command') {
      return COMMANDS.filter(cmd => cmd.value.startsWith(query));
    }
    if (completionContext.type === 'action') {
      return ACTIONS.filter(action => action.value.startsWith(query));
    }
    if (completionContext.type === 'tag') {
      return TAG_OPTIONS
        .filter(tag => tag.startsWith(query))
        .map(tag => ({ type: 'tag' as const, value: tag }));
    }
    if (completionContext.type === 'file') {
      return indexedFiles
        .filter(file => file.toLowerCase().includes(query))
        .slice(0, 8)
        .map(file => ({ type: 'file' as const, value: file }));
    }
    return [];
  }, [completionContext, indexedFiles]);

  const suggestionPrefix = useMemo(() => {
    if (!completionContext) return '';
    switch (completionContext.type) {
      case 'command':
        return '/';
      case 'action':
        return '>';
      case 'file':
        return '@';
      case 'tag':
        return '#';
      default:
        return '';
    }
  }, [completionContext]);

  const applySuggestion = (suggestion: Suggestion) => {
    if (!completionContext) return;
    if (completionContext.type === 'command') {
      setInputValue(`/${suggestion.value} `);
      return;
    }
    if (completionContext.type === 'action') {
      setInputValue(`>${suggestion.value} `);
      return;
    }
    if (completionContext.type === 'file') {
      const before = inputValue.slice(0, completionContext.replaceStart);
      setInputValue(`${before}@${suggestion.value} `);
      return;
    }
    if (completionContext.type === 'tag') {
      const before = inputValue.slice(0, completionContext.replaceStart);
      setInputValue(`${before}#${suggestion.value} `);
    }
  };

  useEffect(() => {
    if (suggestions.length > 0) {
      setSelectedSuggestionIndex(0);
    }
  }, [suggestions]);

  // Handle keyboard shortcuts
  useInput((keyInput, key) => {
    if (key.ctrl && keyInput === 'c') {
      exit();
    }
    if (key.tab && suggestions.length > 0) {
      applySuggestion(suggestions[selectedSuggestionIndex]);
      return;
    }
    if (suggestions.length > 0 && (key.upArrow || key.downArrow)) {
      setSelectedSuggestionIndex(prev => {
        const delta = key.upArrow ? -1 : 1;
        const next = prev + delta;
        if (next < 0) return suggestions.length - 1;
        if (next >= suggestions.length) return 0;
        return next;
      });
      return;
    }
    if (inputValue.length === 0) {
      if (keyInput === 'i') {
        setShowInbox(prev => !prev);
      } else if (keyInput === 'c') {
        setShowContext(prev => !prev);
      } else if (keyInput === 'f') {
        toggleFocus();
      } else if (key.upArrow) {
        setSelectedIndex(prev => Math.max(0, prev - 1));
      } else if (key.downArrow) {
        setSelectedIndex(prev => Math.min(inboxItems.length - 1, prev + 1));
      } else if (key.rightArrow) {
        if (selectedItem?.type === 'task') {
          const hasSubtasks = (selectedItem.task.subtasks?.length ?? 0) > 0;
          if (hasSubtasks) {
            setExpandedTasks(prev => {
              const next = new Set(prev);
              next.add(selectedItem.task.id);
              return next;
            });
          }
        }
      } else if (key.leftArrow) {
        if (selectedItem?.type === 'task') {
          setExpandedTasks(prev => {
            const next = new Set(prev);
            next.delete(selectedItem.task.id);
            return next;
          });
        } else if (selectedItem?.type === 'subtask') {
          const parentIndex = taskIndexById.get(selectedItem.task.id);
          if (parentIndex !== undefined) {
            setSelectedIndex(parentIndex);
          }
          setExpandedTasks(prev => {
            const next = new Set(prev);
            next.delete(selectedItem.task.id);
            return next;
          });
        }
      }
    }
  });

  return (
    <Box flexDirection="column" height="100%">
      {/* Header */}
      <Box justifyContent="space-between">
        <Text color="cyan" bold>ADW</Text>
        <Text dimColor>
          Tasks {tasks.length} • Run {runningCount} • Pending {pendingCount} • Blocked {blockedCount} • Failed {failedCount} • Done {doneCount} • Agents {agents.size}
        </Text>
        <Text color={safetyEnabled ? 'green' : 'red'}>
          {safetyEnabled ? 'Safety: OK' : 'Safety: OFF'}
        </Text>
      </Box>

      {/* Separator */}
      <Box marginTop={1}>
        <Text dimColor>{'─'.repeat(50)}</Text>
      </Box>

      {/* Tasks */}
      {showInbox && (
        <Box flexDirection="column" marginTop={1}>
          <Text color="cyan" bold>📋 TASK INBOX</Text>
          <TaskList
            tasks={sortedTasks}
            expanded={expandedTasks}
            selectedTaskId={selectedTaskId}
            selectedSubtaskId={selectedSubtaskId}
            selectedIsNew={selectedIsNew}
            subtitleByTask={subtitleByTask}
            maxItems={8}
            showNew
          />
        </Box>
      )}

      {/* Context */}
      {showContext && (
        <Box flexDirection="column" marginTop={1}>
          <Text color="magenta" bold>🧭 CONTEXT</Text>
          <Text dimColor>{contextSummary}</Text>
          <Text dimColor>{`${planLine} • ${filesLine} • ${testsLine} • ${attachmentsLine}`}</Text>
        </Box>
      )}

      {/* Logs */}
      <Box flexDirection="column" flexGrow={1} marginTop={1}>
        <LogView
          logs={filteredLogs}
          emptyState={selectedSubtaskId ? 'No messages for this subtask yet.' : 'No messages yet.'}
        />
      </Box>

      {/* Separator */}
      <Box>
        <Text dimColor>{'─'.repeat(50)}</Text>
      </Box>

      {/* Input Hint */}
      <Box>
        <Text dimColor>{inputHint}</Text>
      </Box>

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <Box>
          <Text dimColor>Suggestions: </Text>
          {suggestions.map((suggestion, index) => (
            <Text
              key={`${suggestion.type}-${suggestion.value}`}
              color={index === selectedSuggestionIndex ? 'yellow' : 'dim'}
            >
              {suggestionPrefix}{suggestion.value}
              {index < suggestions.length - 1 ? '  ' : ''}
            </Text>
          ))}
          {completionContext?.type === 'file' && isIndexing && (
            <Text dimColor> (indexing...)</Text>
          )}
        </Box>
      )}

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
              value={inputValue}
              onChange={setInputValue}
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
