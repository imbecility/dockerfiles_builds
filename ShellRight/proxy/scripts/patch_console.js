(() => {
    const g = typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : self);
    if (!g.console) return;

    ['debug', 'log', 'info', 'warn', 'error', 'trace'].forEach(method => {
        if (typeof g.console[method] === 'function') {
            const orig = g.console[method];
            const consoleWrapper = function (...args) {
                try {
                    const safeArgs = args.map(arg => {
                        if (arg && arg instanceof Error && Object.getOwnPropertyDescriptor(arg, 'stack')?.get) {
                            return arg.message || 'Error';
                        }
                        return arg;
                    });
                    return orig.apply(this, safeArgs);
                } catch (e) {
                    return orig.apply(this, args);
                }
            };

            if (typeof setNativeToString === 'function') {
                setNativeToString(consoleWrapper, method);
            }
            g.console[method] = consoleWrapper;
        }
    });
})();