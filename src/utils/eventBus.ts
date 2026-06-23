// src/utils/eventBus.ts
// A tiny pub/sub for cross-domain notifications that don't belong in the store
// (e.g. "a wall was added, rebuild its geometry").

type EventHandler<T = unknown> = (payload: T) => void;

class EventBus {
  private handlers = new Map<string, Set<EventHandler>>();

  /** Subscribe; returns an unsubscribe function. */
  on<T>(event: string, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler as EventHandler);
    return () => this.handlers.get(event)?.delete(handler as EventHandler);
  }

  emit<T>(event: string, payload: T): void {
    this.handlers.get(event)?.forEach((handler) => handler(payload));
  }
}

export const eventBus = new EventBus();
// Editor:  eventBus.emit('wall:added', { wallId });
// Viewer:  eventBus.on<{ wallId: string }>('wall:added', ({ wallId }) => rebuild(wallId));
