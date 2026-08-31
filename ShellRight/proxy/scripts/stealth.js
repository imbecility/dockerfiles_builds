(() => {
    if (window.__stealth_injected__) return;
    window.__stealth_injected__ = true;

    const VENDOR = '__VENDOR__';
    const RENDERER = '__RENDERER__';
    const RESOLUTION_MS = __TIMER_RES__;

    // 1. Огрубление performance.now() до реалистичного разрешения Chrome
    // (Fix hasInconsistentTimingResolution без накопительного дрейфа)
    try {
        if (window.performance && window.performance.now) {
            const origNow = performance.now.bind(performance);
            // 0.1ms — типичное разрешение огрублённого таймера в обычном
            // (не cross-origin-isolated) контексте настоящего Chrome.
            const patchedNow = function () {
                const real = origNow();
                return Math.floor(real / RESOLUTION_MS) * RESOLUTION_MS;
            };
            setNativeToString(patchedNow, 'now');
            performance.now = patchedNow;
        }
    } catch (e) {}


    // 2. Детерминированное удаление WebGPU без гонки инициализации адаптера
    try {
        if ('gpu' in Navigator.prototype) {
            delete Navigator.prototype.gpu;
        }
        Object.defineProperty(Navigator.prototype, 'gpu', {
            get: () => undefined,
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    // 2. Безопасная маскировка toString() -> [native code]
    const nativeToString = Function.prototype.toString;
    const customToStringMap = new WeakMap();

    function setNativeToString(fn, name) {
        if (typeof fn === 'function') {
            customToStringMap.set(fn, 'function ' + (name || fn.name || '') + '() { [native code] }');
        }
    }

    Function.prototype.toString = function () {
        if (typeof this === 'function' && customToStringMap.has(this)) {
            return customToStringMap.get(this);
        }
        return nativeToString.apply(this, arguments);
    };
    setNativeToString(Function.prototype.toString, 'toString');

    // 3. Webdriver
    try {
        if (Navigator.prototype.hasOwnProperty('webdriver')) {
            delete Navigator.prototype.webdriver;
        }
        const webdriverGetter = function () {
            return undefined;
        };
        setNativeToString(webdriverGetter, 'get webdriver');
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: webdriverGetter,
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    // 4. PDF Viewer
    try {
        const pdfGetter = function () {
            return true;
        };
        setNativeToString(pdfGetter, 'get pdfViewerEnabled');
        Object.defineProperty(Navigator.prototype, 'pdfViewerEnabled', {
            get: pdfGetter,
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    // 5. Плагины (двусторонняя связь Plugin <-> MimeType)
    try {
        const pluginData = [
            {
                name: 'PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}]
            },
            {
                name: 'Chrome PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}]
            },
            {
                name: 'Chromium PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}]
            },
            {
                name: 'Microsoft Edge PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}]
            },
            {
                name: 'WebKit built-in PDF',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [{type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'}]
            }
        ];

        const pArr = [];
        const mArr = [];

        pluginData.forEach((pInfo, pIdx) => {
            const plugin = [];
            plugin.name = pInfo.name;
            plugin.filename = pInfo.filename;
            plugin.description = pInfo.description;

            pInfo.mimeTypes.forEach((mInfo, mIdx) => {
                const mime = {
                    type: mInfo.type,
                    suffixes: mInfo.suffixes,
                    description: mInfo.description,
                    enabledPlugin: plugin
                };
                if (typeof MimeType !== 'undefined') Object.setPrototypeOf(mime, MimeType.prototype);
                plugin[mIdx] = mime;
                plugin[mInfo.type] = mime;
                mArr.push(mime);
                mArr[mInfo.type] = mime;
            });

            const pItem = function (i) {
                return this[i] || null;
            };
            const pNamed = function (n) {
                return this[n] || null;
            };
            setNativeToString(pItem, 'item');
            setNativeToString(pNamed, 'namedItem');
            plugin.item = pItem;
            plugin.namedItem = pNamed;
            if (typeof Plugin !== 'undefined') Object.setPrototypeOf(plugin, Plugin.prototype);

            pArr[pIdx] = plugin;
            pArr[pInfo.name] = plugin;
        });

        const arrItem = function (i) {
            return this[i] || null;
        };
        const arrNamed = function (n) {
            return this[n] || null;
        };
        const arrRefresh = function () {
        };
        setNativeToString(arrItem, 'item');
        setNativeToString(arrNamed, 'namedItem');
        setNativeToString(arrRefresh, 'refresh');
        pArr.item = arrItem;
        pArr.namedItem = arrNamed;
        pArr.refresh = arrRefresh;
        if (typeof PluginArray !== 'undefined') Object.setPrototypeOf(pArr, PluginArray.prototype);

        const mItem = function (i) {
            return this[i] || null;
        };
        const mNamed = function (n) {
            return this[n] || null;
        };
        setNativeToString(mItem, 'item');
        setNativeToString(mNamed, 'namedItem');
        mArr.item = mItem;
        mArr.namedItem = mNamed;
        if (typeof MimeTypeArray !== 'undefined') Object.setPrototypeOf(mArr, MimeTypeArray.prototype);

        const pluginsGetter = function () {
            return pArr;
        };
        const mimesGetter = function () {
            return mArr;
        };
        setNativeToString(pluginsGetter, 'get plugins');
        setNativeToString(mimesGetter, 'get mimeTypes');

        Object.defineProperty(Navigator.prototype, 'plugins', {
            get: pluginsGetter,
            configurable: true,
            enumerable: true
        });
        Object.defineProperty(Navigator.prototype, 'mimeTypes', {
            get: mimesGetter,
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    // 6. Notification & Permissions (гарантированный resolve для Google reCAPTCHA)
    try {
        if (typeof Notification !== 'undefined') {
            const permGetter = function () {
                return 'default';
            };
            setNativeToString(permGetter, 'get permission');
            Object.defineProperty(Notification, 'permission', {
                get: permGetter,
                configurable: true,
                enumerable: true
            });
        }

        if (window.navigator.permissions && window.navigator.permissions.query) {
            const origQuery = window.navigator.permissions.query;
            const queryWrapper = function (params) {
                if (params && params.name === 'notifications') {
                    return origQuery.apply(this, arguments).then(status => {
                        try {
                            const stateGetter = function () {
                                return 'prompt';
                            };
                            setNativeToString(stateGetter, 'get state');
                            Object.defineProperty(status, 'state', {
                                get: stateGetter,
                                configurable: true,
                                enumerable: true
                            });
                        } catch (e) {
                        }
                        return status;
                    }).catch(() => {
                        const dummy = Object.create(PermissionStatus.prototype);
                        Object.defineProperty(dummy, 'state', {
                            get: () => 'prompt',
                            configurable: true,
                            enumerable: true
                        });
                        dummy.onchange = null;
                        return dummy;
                    });
                }
                return origQuery.apply(this, arguments);
            };
            setNativeToString(queryWrapper, 'query');
            window.navigator.permissions.query = queryWrapper;
        }
    } catch (e) {}

    // 7. Динамические самосогласованные размеры Window & Screen (Fix overflowTest & PHANTOM_WINDOW_HEIGHT)
    try {
        const TOOLBAR_H = 85;
        const TASKBAR_H = 40;

        const owGetter = function () {
            return window.innerWidth;
        };
        const ohGetter = function () {
            return window.innerHeight + TOOLBAR_H;
        };
        setNativeToString(owGetter, 'get outerWidth');
        setNativeToString(ohGetter, 'get outerHeight');

        Object.defineProperty(window, 'outerWidth', {get: owGetter, configurable: true, enumerable: true});
        Object.defineProperty(window, 'outerHeight', {get: ohGetter, configurable: true, enumerable: true});

        if (typeof Screen !== 'undefined') {
            const wGetter = function () {
                return window.innerWidth;
            };
            const hGetter = function () {
                return window.innerHeight + TOOLBAR_H + TASKBAR_H;
            };
            const awGetter = function () {
                return window.innerWidth;
            };
            const ahGetter = function () {
                return window.innerHeight + TOOLBAR_H;
            };
            const cdGetter = function () {
                return 24;
            };

            setNativeToString(wGetter, 'get width');
            setNativeToString(hGetter, 'get height');
            setNativeToString(awGetter, 'get availWidth');
            setNativeToString(ahGetter, 'get availHeight');
            setNativeToString(cdGetter, 'get colorDepth');

            Object.defineProperty(Screen.prototype, 'width', {get: wGetter, configurable: true, enumerable: true});
            Object.defineProperty(Screen.prototype, 'height', {get: hGetter, configurable: true, enumerable: true});
            Object.defineProperty(Screen.prototype, 'availWidth', {
                get: awGetter,
                configurable: true,
                enumerable: true
            });
            Object.defineProperty(Screen.prototype, 'availHeight', {
                get: ahGetter,
                configurable: true,
                enumerable: true
            });
            Object.defineProperty(Screen.prototype, 'colorDepth', {
                get: cdGetter,
                configurable: true,
                enumerable: true
            });
            Object.defineProperty(Screen.prototype, 'pixelDepth', {
                get: cdGetter,
                configurable: true,
                enumerable: true
            });
        }
    } catch (e) {}

    // 8. Спуфинг WebGL в DOM
    try {
        const spoofWebGL = (proto) => {
            if (!proto || !proto.getParameter) return;
            const origGetParam = proto.getParameter;
            const getParamWrapper = function (param) {
                if (param === 37445) return VENDOR;
                if (param === 37446) return RENDERER;
                return origGetParam.apply(this, arguments);
            };
            setNativeToString(getParamWrapper, 'getParameter');
            proto.getParameter = getParamWrapper;
        };
        if (typeof WebGLRenderingContext !== 'undefined') spoofWebGL(WebGLRenderingContext.prototype);
        if (typeof WebGL2RenderingContext !== 'undefined') spoofWebGL(WebGL2RenderingContext.prototype);
    } catch (e) {}

    // 9. window.chrome
    try {
        if (!window.chrome) {
            const csiFn = function csi() {
            };
            const ltFn = function loadTimes() {
                return {};
            };
            setNativeToString(csiFn, 'csi');
            setNativeToString(ltFn, 'loadTimes');
            window.chrome = {
                app: {isInstalled: false},
                runtime: {},
                csi: csiFn,
                loadTimes: ltFn
            };
        }
    } catch (e) {}

    // 10. Защита от CDP Console (isAutomatedWithCDP)
    try { __PATCH_CONSOLE__ } catch (e) {}
})();