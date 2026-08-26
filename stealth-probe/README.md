# stealth-probe

Чисто статическая страница, ничего не требует кроме хостинга файла `index.html`.

## Деплой (проще всего — GitHub Pages)

1. Включите Pages в настройках репозитория: **Settings → Pages → Source: Deploy from branch → /stealth-probe**
   (или через отдельный `gh-pages` branch / отдельный репозиторий — на ваш выбор).
2. Получите итоговый URL вида `https://<user>.github.io/<repo>/` или `https://<user>.github.io/<repo>/stealth-probe/`.
3. Пропишите его в `shared/detection_parsers.py`:

   ```python
   STEALTH_PROBE_URL = "https://<ваш-url>/"
   ```

## Что проверяет страница

- `navigator.webdriver`, `window.chrome`, UA на признаки headless/бот-паттернов
- утечки автоматизации (`cdc_*`, `__webdriver*`, `__selenium*` и т.д. в `window`)
- нативность встроенных функций (`Function.prototype.toString`)
- работоспособность canvas (заблокированный/пустой canvas — частый tell)
- согласованность WebGL vendor/renderer (обычный и `UNMASKED_*`)
- дефолтное headless-разрешение экрана (800x600 / `outerWidth === 0`)
- `hardwareConcurrency`
- разрешение таймеров (`performance.now()` без джиттера — tell автоматизации)

Результат кладётся в `#jsonResult` (тот же формат, что и на deviceandbrowserinfo.com) и в
`window.__stealthProbeResult`, чтобы `page.evaluate("window.__stealthProbeResult")` не требовал
повторного парсинга текста.
