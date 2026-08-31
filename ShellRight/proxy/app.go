package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

// App связывает супервайзер браузера (опциональный) и CDP-прокси и отвечает
// за их совместный запуск и корректную остановку. Раньше вся эта
// оркестрация — включая выбор proxy-only/managed-browser режима и
// graceful shutdown — жила прямо в func main() вперемешку с чтением
// конфигурации; вынесение в отдельный тип делает жизненный цикл процесса
// явным и проверяемым отдельно от точки входа.
type App struct {
	cfg *Config

	supervisor *ChromeSupervisor
	proxy      *Proxy
	server     *http.Server
}

// NewApp собирает App из конфигурации. Если бинарник Chrome не найден по
// cfg.ChromeBin, супервайзер не создаётся, и прокси работает в режиме
// proxy-only, подключаясь к Chromium, запущенному где-то ещё.
func NewApp(ctx context.Context, cfg *Config) *App {
	app := &App{cfg: cfg}

	switch _, err := os.Stat(cfg.ChromeBin); {
	case err == nil:
		app.supervisor = NewChromeSupervisor(ctx, cfg)
	case os.IsNotExist(err):
		log.Printf("[Main] Chrome binary not found at %s. Running in proxy-only mode.", cfg.ChromeBin)
	default:
		// Отдельная ветка для ошибок помимо "файла нет" (например, нет прав
		// на бинарник) — раньше такие ошибки молча трактовались как
		// "не найден", что маскировало реальную проблему в логах.
		log.Printf("[Main] Could not stat Chrome binary at %s (%v). Running in proxy-only mode.", cfg.ChromeBin, err)
	}

	app.proxy = NewProxy(cfg)
	app.server = &http.Server{
		Addr:    cfg.ListenAddr,
		Handler: app.proxy.Handler(),
	}

	return app
}

// Run запускает супервайзер (если он есть) и прокси, блокируясь до отмены
// ctx или до ошибки сервера, и в любом случае останавливает всё перед
// выходом — см. shutdown(). Раньше и неготовность Chrome, и ошибка
// ListenAndServe обрабатывались через log.Fatalf прямо в месте
// возникновения (в одном случае — в горутине), из-за чего os.Exit
// срабатывал в обход отложенной остановки уже запущенного процесса Chrome.
// Теперь Run только возвращает ошибку, а cleanup гарантирован через defer.
func (a *App) Run(ctx context.Context) error {
	defer a.shutdown()

	if a.supervisor != nil {
		a.supervisor.Start()

		log.Println("[Main] Waiting for Chrome CDP to become ready...")
		if err := a.supervisor.WaitReady(15*time.Second, a.cfg.UpstreamHTTP); err != nil {
			return fmt.Errorf("chrome readiness failed: %w", err)
		}
		log.Println("[Main] Chrome CDP is ready.")
	}

	serveErr := make(chan error, 1)
	go func() {
		log.Printf("[Main] CDP Stealth Proxy listening on %s -> %s", a.cfg.ListenAddr, a.cfg.UpstreamHTTP)
		if err := a.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serveErr <- err
			return
		}
		serveErr <- nil
	}()

	select {
	case <-ctx.Done():
		log.Println("[Main] Shutting down gracefully...")
		return nil
	case err := <-serveErr:
		return err
	}
}

// shutdown корректно останавливает прокси-сервер и (если запущен) браузер.
// Вызывается через defer в Run, так что срабатывает на любом пути выхода —
// по сигналу, по ошибке сервера или по неготовности Chrome.
func (a *App) shutdown() {
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	_ = a.server.Shutdown(shutdownCtx)

	if a.supervisor != nil {
		a.supervisor.Stop()
	}

	log.Println("[Main] Server stopped cleanly.")
}
