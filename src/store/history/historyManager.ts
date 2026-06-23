// src/store/history/historyManager.ts

import type { Command } from './commands';

const MAX_HISTORY_SIZE = 100;

/**
 * Past/future command stacks. Commands (not full snapshots) are stored, so memory stays
 * small. Batches group related ops (e.g. a wall split = create vertex + 2 walls) into one
 * undo unit. Starting a new action clears the redo (future) stack.
 */
export class HistoryManager {
  private past: Command[] = [];
  private future: Command[] = [];
  private batchQueue: Command[] | null = null;
  private maxSize: number;

  constructor(maxSize = MAX_HISTORY_SIZE) {
    this.maxSize = maxSize;
  }

  execute(command: Command): void {
    command.execute();
    if (this.batchQueue) {
      this.batchQueue.push(command);
      return;
    }
    this.past.push(command);
    this.future = [];
    if (this.past.length > this.maxSize) this.past.shift();
  }

  undo(): boolean {
    const command = this.past.pop();
    if (!command) return false;
    command.undo();
    this.future.push(command);
    return true;
  }

  redo(): boolean {
    const command = this.future.pop();
    if (!command) return false;
    command.execute();
    this.past.push(command);
    return true;
  }

  beginBatch(_label: string): void {
    this.batchQueue = [];
  }

  endBatch(label: string): void {
    if (!this.batchQueue || this.batchQueue.length === 0) {
      this.batchQueue = null;
      return;
    }
    const commands = [...this.batchQueue];
    this.batchQueue = null;
    const batch: Command = {
      type: 'BATCH',
      label,
      timestamp: Date.now(),
      execute: () => commands.forEach((c) => c.execute()),
      undo: () => [...commands].reverse().forEach((c) => c.undo()),
    };
    this.past.push(batch);
    this.future = [];
    if (this.past.length > this.maxSize) this.past.shift();
  }

  cancelBatch(): void {
    if (!this.batchQueue) return;
    [...this.batchQueue].reverse().forEach((c) => c.undo());
    this.batchQueue = null;
  }

  get canUndo(): boolean { return this.past.length > 0; }
  get canRedo(): boolean { return this.future.length > 0; }
  get undoLabel(): string | null { return this.past.at(-1)?.label ?? null; }
  get redoLabel(): string | null { return this.future.at(-1)?.label ?? null; }
  get historySize(): number { return this.past.length; }

  clear(): void {
    this.past = [];
    this.future = [];
    this.batchQueue = null;
  }
}
