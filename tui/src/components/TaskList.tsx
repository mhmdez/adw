import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { Task, Subtask } from '../hooks/useTasks.js';

interface TaskListProps {
  tasks: Task[];
  expanded: Set<string>;
  selectedTaskId?: string;
  selectedSubtaskId?: string;
  selectedIsNew?: boolean;
  subtitleByTask?: Record<string, string>;
  maxItems?: number;
  showNew?: boolean;
}

export function TaskList({
  tasks,
  expanded,
  selectedTaskId,
  selectedSubtaskId,
  selectedIsNew,
  subtitleByTask = {},
  maxItems = 10,
  showNew = false,
}: TaskListProps) {
  const display = tasks.slice(0, maxItems);
  const remaining = tasks.length - display.length;

  return (
    <Box flexDirection="column">
      {display.length === 0 && (
        <Text dimColor>  No tasks yet</Text>
      )}
      {display.map(task => (
        <Box key={task.id} flexDirection="column">
          <TaskItem
            task={task}
            expanded={expanded.has(task.id)}
            selected={selectedTaskId === task.id && !selectedSubtaskId}
            subtitle={subtitleByTask[task.id]}
          />
          {expanded.has(task.id) && (task.subtasks ?? []).map(subtask => (
            <SubtaskItem
              key={subtask.id}
              subtask={subtask}
              selected={selectedSubtaskId === subtask.id}
            />
          ))}
        </Box>
      ))}
      {remaining > 0 && (
        <Text dimColor>  ... and {remaining} more</Text>
      )}
      {showNew && (
        <NewTaskItem selected={!!selectedIsNew} />
      )}
    </Box>
  );
}

interface TaskItemProps {
  task: Task;
  expanded: boolean;
  selected: boolean;
  subtitle?: string;
}

function TaskItem({ task, expanded, selected, subtitle }: TaskItemProps) {
  const shortId = task.id.slice(0, 8);
  const desc = task.description.length > 50
    ? task.description.slice(0, 47) + '...'
    : task.description;
  const hasSubtasks = (task.subtasks?.length ?? 0) > 0;

  return (
    <Box flexDirection="column">
      <Box>
        <Text color={selected ? 'yellow' : undefined}>{selected ? '›' : ' '}</Text>
        <Text dimColor> </Text>
        <Text dimColor>{hasSubtasks ? (expanded ? '▾' : '▸') : ' '} </Text>
        <StatusIcon status={task.status} />
        <Text dimColor> {shortId} </Text>
        <TaskText status={task.status} text={desc} />
      </Box>
      {subtitle && (
        <Box marginLeft={5}>
          <Text dimColor>{subtitle.slice(0, 80)}</Text>
        </Box>
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

function SubtaskItem({ subtask, selected }: { subtask: Subtask; selected: boolean }) {
  const done = subtask.status === 'done';
  return (
    <Box marginLeft={4}>
      <Text color={selected ? 'yellow' : undefined}>{selected ? '›' : ' '}</Text>
      <Text dimColor> </Text>
      <Text color={done ? 'green' : 'dim'}>{done ? '✓' : '○'}</Text>
      <Text dimColor> {subtask.title.slice(0, 70)}</Text>
    </Box>
  );
}

function NewTaskItem({ selected }: { selected: boolean }) {
  return (
    <Box>
      <Text color={selected ? 'yellow' : undefined}>{selected ? '›' : ' '}</Text>
      <Text dimColor> </Text>
      <Text color="green">＋</Text>
      <Text dimColor> New task</Text>
    </Box>
  );
}
