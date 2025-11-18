// Polyfills for Node.js globals required by some packages (e.g., Stoplight Elements)

// Polyfill for process
if (typeof window !== 'undefined' && !(window as any).process) {
  (window as any).process = {
    env: {},
    version: '',
    platform: 'browser',
    nextTick: (fn: Function) => Promise.resolve().then(() => fn()),
  };
}

// Polyfill for global
if (typeof window !== 'undefined' && !(window as any).global) {
  (window as any).global = window;
}
