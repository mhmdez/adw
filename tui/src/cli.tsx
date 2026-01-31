#!/usr/bin/env node
import React from 'react';
import { render } from 'ink';
import meow from 'meow';
import { App } from './App.js';

const cli = meow(`
  Usage
    $ adw-tui

  Options
    --help     Show help
    --version  Show version

  Commands
    Type /help in the TUI for available commands
`, {
  importMeta: import.meta,
  flags: {}
});

const cwd = process.cwd();

// Clear screen and render
console.clear();

const { waitUntilExit } = render(<App cwd={cwd} />);

waitUntilExit().then(() => {
  process.exit(0);
});
