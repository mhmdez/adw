import test from 'node:test';
import assert from 'node:assert/strict';
import { __test__ } from '../src/hooks/useAgents.ts';

test('formatEventMessage uses message when present', () => {
  const data = __test__.parseEventData('{"message":"Tool started"}');
  const message = __test__.formatEventMessage('tool_start', data);
  assert.equal(message, 'tool start: Tool started');
});

test('formatEventMessage uses tool_name when message missing', () => {
  const data = { tool_name: 'git status' };
  const message = __test__.formatEventMessage('tool_start', data);
  assert.equal(message, 'tool start: git status');
});

test('eventLogType maps errors to error', () => {
  assert.equal(__test__.eventLogType('task_failed'), 'error');
  assert.equal(__test__.eventLogType('tool_error'), 'error');
});
