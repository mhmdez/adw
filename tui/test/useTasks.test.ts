import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { __test__ } from '../src/hooks/useTasks.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));

test('parseTasks handles legacy and list task formats', () => {
  const fixturePath = join(__dirname, 'fixtures', 'tasks.md');
  const content = readFileSync(fixturePath, 'utf-8');
  const tasks = __test__.parseTasks(content);

  assert.equal(tasks.length, 4);

  const first = tasks[0];
  assert.equal(first.id, 'TASK-001');
  assert.equal(first.status, 'done');
  assert.equal(first.adwId, 'b534c104');
  assert.deepEqual(first.tags, ['vkg', 'high']);
  assert.equal(first.description, 'Initialize VKG structure');

  const second = tasks[1];
  assert.equal(second.id, 'TASK-002');
  assert.equal(second.status, 'in_progress');
  assert.equal(second.adwId, 'a1b2c3d4');
  assert.deepEqual(second.tags, ['p1']);

  const third = tasks[2];
  assert.equal(third.id, 'TASK-003');
  assert.equal(third.status, 'pending');

  const fourth = tasks[3];
  assert.equal(fourth.id, 'TASK-004');
  assert.equal(fourth.status, 'done');
  assert.ok(fourth.subtasks && fourth.subtasks.length === 1);
});

test('insertTaskLine places new tasks in Active Tasks section', () => {
  const fixturePath = join(__dirname, 'fixtures', 'tasks.md');
  const content = readFileSync(fixturePath, 'utf-8');
  const nextLine = '[ ] **TASK-005**: Ship parser hardening {chore}';
  const updated = __test__.insertTaskLine(content, nextLine);

  assert.ok(updated.includes(nextLine));
  const activeIndex = updated.indexOf('## Active Tasks');
  const insertedIndex = updated.indexOf(nextLine);
  assert.ok(insertedIndex > activeIndex);
});
