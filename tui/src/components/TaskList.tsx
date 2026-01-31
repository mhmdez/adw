import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { Task } from '../hooks/useTasks.js';

interface TaskListProps {
  tasks: Task[];
  maxItems?: number;
}

export function TaskList({ tasks, maxItems = 10 }: TaskListProps) {
  // Sort: running first, then pending, then done
  const sorted = [...tasks].sort((a, b) => {
    const order: Record<string, number> = {
      'in_progress': 0,
      'pending': 1,
      'blocked': 2,
      'failed': 3,
      'done': 4,
    };
    return (order[a.status] ?? 5) - (order[b.status] ?? 5);
  });

  const display = sorted.slice(0, maxItems);
  const remaining = sorted.length - display.length;

  return (
    <Box flexDirection="column">
      {display.map(task => (
        <TaskItem key={task.id} task={task} />
      ))}
      {remaining > 0 && (
        <Text dimColor>  ... and {remaining} more</Text>
      )}
    </Box>
  );
}

interface TaskItemProps {
  task: Task;
}

function TaskItem({ task }: TaskItemProps) {
  const shortId = task.id.slice(0, 8);
  const desc = task.description.length > 50
    ? task.description.slice(0, 47) + '...'
    : task.description;

  return (
    <Box>
      <StatusIcon status={task.status} />
      <Text dimColor> {shortId} </Text>
      <TaskText status={task.status} text={desc} />
      {task.activity && (
        <Text dimColor italic> - {task.activity.slice(0, 20)}</Text>
      )}
    </Box>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'in_progress':
      return (
        <Text color="cyan">
          <Spinner type="dots" />
        </Text>
      );
    case 'done':
      return <Text color="green">✓</Text>;
    case 'failed':
      return <Text color="red">✗</Text>;
    case 'blocked':
      return <Text color="yellow">◷</Text>;
    default:
      return <Text dimColor>○</Text>;
  }
}

function TaskText({ status, text }: { status: string; text: string }) {
  switch (status) {
    case 'in_progress':
      return <Text color="cyan">{text}</Text>;
    case 'done':
      return <Text color="green">{text}</Text>;
    case 'failed':
      return <Text color="red">{text}</Text>;
    default:
      return <Text>{text}</Text>;
  }
}
