/*
CDP-Proxy — прозрачный обратный прокси для Chrome DevTools Protocol (CDP).
Автоматически инжектирует stealth-скрипты в страницы и воркеры, маскируя автоматизацию.

Переменные окружения:

	CHROME_BIN
		Путь до бинарника браузера
		По умолчанию: /opt/headless-shell/chrome-headless-shell

	CHROME_HTTP
		HTTP-адрес Chromium апстрима.
		По умолчанию: http://127.0.0.1:9222

	CHROME_WS
		WebSocket-адрес Chromium апстрима.
		По умолчанию: ws://127.0.0.1:9222

	PROXY_LISTEN
		Сетевой интерфейс и порт, на котором прокси принимает соединения.
		По умолчанию: :9223

	PROXY_PUBLIC_HOST
		Хост/порт, подставляемый в ответы Chromium (/json/list и др.),
		чтобы клиенты подключались к прокси, а не напрямую к браузеру.
		По умолчанию: localhost:9223
*/
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	cfg := LoadConfig()

	// Контекст для перехвата системных сигналов завершения контейнера (SIGTERM/SIGINT)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	app := NewApp(ctx, cfg)
	if err := app.Run(ctx); err != nil {
		log.Fatalf("[Main] %v", err)
	}
}
