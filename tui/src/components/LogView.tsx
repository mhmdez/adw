import React from 'react';
import { Box, Text } from 'ink';
import { LogEntry } from '../hooks/useLogs.js';

interface LogViewProps {
  logs: LogEntry[];
  maxLines?: number;
  emptyState?: string;
}

export function LogView({ logs, maxLines = 20, emptyState = 'No messages yet.' }: LogViewProps) {
  const display = logs.slice(-maxLines);

  return (
    <Box flexDirection="column">
      {display.length === 0 ? (
        <Text dimColor>{emptyState}</Text>
      ) : (
        display.map((log, i) => (
          <LogLine key={i} log={log} />
        ))
      )}
    </Box>
  );
}

function LogLine({ log }: { log: LogEntry }) {
  const time = log.timestamp.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  switch (log.type) {
    case 'user':
      return (
        <Box>
          <Text bold color="green">&gt; </Text>
          <Text>{log.message}</Text>
        </Box>
      );

    case 'assistant':
      return (
        <Box flexDirection="column">
          {log.message.split('\n').map((line, i) => (
            <Text key={i}>{line}</Text>
          ))}
        </Box>
      );

    case 'system':
      return <Text dimColor>{log.message}</Text>;

    case 'error':
      return <Text color="red">{log.message}</Text>;

    case 'tool':
      return (
        <Box>
          <Text dimColor>{time} </Text>
          <Text color="cyan">🔧 </Text>
          <Text dimColor>[{log.agentId?.slice(0, 8)}] </Text>
          <Text>{log.message}</Text>
        </Box>
      );

    case 'agent':
      return (
        <Box>
          <Text dimColor>{time} </Text>
          <Text color="blue">💬 </Text>
          <Text dimColor>[{log.agentId?.slice(0, 8)}] </Text>
          <Text>{log.message}</Text>
        </Box>
      );

    default:
      return <Text>{log.message}</Text>;
  }
}
