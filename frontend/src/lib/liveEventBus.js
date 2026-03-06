export function createLiveEventBus() {
  const listeners = new Map();

  return {
    on(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, new Set());
      }
      listeners.get(type).add(handler);
      return () => {
        const handlers = listeners.get(type);
        if (!handlers) {
          return;
        }
        handlers.delete(handler);
        if (!handlers.size) {
          listeners.delete(type);
        }
      };
    },

    emit(type, payload) {
      const handlers = listeners.get(type);
      if (!handlers?.size) {
        return;
      }
      for (const handler of handlers) {
        handler(payload);
      }
    },

    clear() {
      listeners.clear();
    },
  };
}
