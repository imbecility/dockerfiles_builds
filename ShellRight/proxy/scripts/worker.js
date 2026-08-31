try {
    const VENDOR = '__VENDOR__';
    const RENDERER = '__RENDERER__';
    const RESOLUTION_MS = __TIMER_RES__;

    // 1. Огрубление performance.now() в воркере
    try {
        if (typeof performance !== 'undefined' && performance.now) {
            const origNow = performance.now.bind(performance);
            performance.now = function () {
                return Math.floor(origNow() / RESOLUTION_MS) * RESOLUTION_MS;
            };
        }
    } catch (e) {}

    // 2. Свойства WorkerNavigator
    if (typeof WorkerNavigator !== 'undefined') {
        if (WorkerNavigator.prototype.hasOwnProperty('webdriver')) {
            delete WorkerNavigator.prototype.webdriver;
        }
        Object.defineProperty(WorkerNavigator.prototype, 'webdriver', {
            get: () => undefined, configurable: true, enumerable: true
        });
        Object.defineProperty(WorkerNavigator.prototype, 'pdfViewerEnabled', {
            get: () => true, configurable: true, enumerable: true
        });
    }

    // 3. OffscreenCanvas WebGL
    if (typeof OffscreenCanvas !== 'undefined' && OffscreenCanvas.prototype.getContext) {
        const origGetContext = OffscreenCanvas.prototype.getContext;
        OffscreenCanvas.prototype.getContext = function (type, ...args) {
            const ctx = origGetContext.call(this, type, ...args);
            if (ctx && (type === 'webgl' || type === 'webgl2')) {
                const origGetParam = ctx.getParameter;
                ctx.getParameter = function (param) {
                    if (param === 37445) return VENDOR;
                    if (param === 37446) return RENDERER;
                    return origGetParam.apply(this, arguments);
                };
            }
            return ctx;
        };
    }

    // 3. Защита от CDP Console (вынесенный общий модуль)
    try {
        __PATCH_CONSOLE__
    } catch (e) {}
} catch (e) {}