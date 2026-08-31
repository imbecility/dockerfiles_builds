package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os/exec"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ChromeSupervisor управляет жизненным циклом процесса chrome-headless-shell.
type ChromeSupervisor struct {
	binPath string
	flags   []string

	ctx    context.Context
	cancel context.CancelFunc

	wg sync.WaitGroup
}

// NewChromeSupervisor инициализирует супервайзер и вычисляет версию бинарника.
// Адрес и порт для --remote-debugging-* берутся из cfg.UpstreamHTTP — того
// же URL, на который затем ходит прокси — а не захардкожены отдельно: иначе
// при смене CHROME_HTTP/CHROME_WS Chrome продолжил бы слушать старый порт,
// и WaitReady/прокси перестали бы его находить.
func NewChromeSupervisor(ctx context.Context, cfg *Config) *ChromeSupervisor {
	cCtx, cancel := context.WithCancel(ctx)

	version := detectChromeVersion(cfg.ChromeBin)
	log.Printf("[Supervisor] Detected Chrome version: %s", version)

	ua := fmt.Sprintf("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36", version)

	debugAddr, debugPort := debugHostPort(cfg.UpstreamHTTP)

	flags := []string{
		"--headless",
		"--enable-unsafe-swiftshader",
		"--disable-features=WebGPU",
		"--no-sandbox",
		"--disable-setuid-sandbox",
		"--disable-dev-shm-usage",
		"--disable-blink-features=AutomationControlled",
		"--remote-debugging-address=" + debugAddr,
		"--remote-debugging-port=" + debugPort,
		"--no-first-run",
		"--no-default-browser-check",
		"--window-size=1920,1080",
		"--lang=en-US,en",
		"--user-agent=" + ua,
	}

	return &ChromeSupervisor{
		binPath: cfg.ChromeBin,
		flags:   flags,
		ctx:     cCtx,
		cancel:  cancel,
	}
}

// debugHostPort достаёт хост и порт для флагов --remote-debugging-* из URL
// апстрима (например, "http://127.0.0.1:9222"). Если разобрать не удалось —
// возвращает те же значения, что раньше были захардкожены во флагах, так что
// поведение по умолчанию не меняется.
func debugHostPort(rawURL string) (addr, port string) {
	addr, port = "127.0.0.1", "9222"
	u, err := url.Parse(rawURL)
	if err != nil {
		return addr, port
	}
	if h := u.Hostname(); h != "" {
		addr = h
	}
	if p := u.Port(); p != "" {
		port = p
	}
	return addr, port
}

// Start запускает цикл супервайзера в фоновой горутине.
func (s *ChromeSupervisor) Start() {
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		s.supervise()
	}()
}

func (s *ChromeSupervisor) supervise() {
	for {
		select {
		case <-s.ctx.Done():
			return
		default:
		}

		cmd := exec.CommandContext(s.ctx, s.binPath, s.flags...)

		// Мягкая остановка
		cmd.Cancel = func() error {
			return cmd.Process.Signal(syscall.SIGTERM)
		}
		cmd.WaitDelay = 3 * time.Second // Если не вышел за 3с -> SIGKILL

		// Перенаправляем логи Chromium в stdout с префиксом
		stdout, _ := cmd.StdoutPipe()
		stderr, _ := cmd.StderrPipe()
		go pipeLogs("[Chrome] ", stdout)
		go pipeLogs("[Chrome] ", stderr)

		log.Printf("[Supervisor] Starting %s...", s.binPath)
		if err := cmd.Start(); err != nil {
			log.Printf("[Supervisor] Failed to start Chrome: %v", err)
			time.Sleep(1 * time.Second)
			continue
		}

		log.Printf("[Supervisor] Chrome started (PID: %d)", cmd.Process.Pid)

		// Ждем завершения процесса (при s.cancel() здесь сработает cmd.Cancel)
		err := cmd.Wait()

		select {
		case <-s.ctx.Done():
			// Остановка была плановой — выходим из цикла
			return
		default:
			log.Printf("[Supervisor] Chrome exited unexpectedly (%v). Restarting in 500ms...", err)
			time.Sleep(500 * time.Millisecond)
		}
	}
}

// WaitReady блокирует выполнение, пока эндпоинт отладки не ответит HTTP 200.
func (s *ChromeSupervisor) WaitReady(timeout time.Duration, endpoint string) error {
	client := &http.Client{Timeout: 500 * time.Millisecond}
	deadline := time.Now().Add(timeout)

	for time.Now().Before(deadline) {
		select {
		case <-s.ctx.Done():
			return s.ctx.Err()
		default:
		}

		resp, err := client.Get(endpoint + "/json/version")
		if err == nil && resp.StatusCode == http.StatusOK {
			_ = resp.Body.Close()
			return nil
		}
		if resp != nil {
			_ = resp.Body.Close()
		}
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Errorf("chrome did not become ready within %v", timeout)
}

// Stop инициирует остановку и блокируется до полного завершения процесса браузера.
func (s *ChromeSupervisor) Stop() {
	s.cancel()
	s.wg.Wait() // Гарантирует, что main() не завершится раньше времени
}

func detectChromeVersion(binPath string) string {
	out, err := exec.Command(binPath, "--version").Output()
	if err != nil {
		return "133.0.0.0"
	}
	re := regexp.MustCompile(`\d+\.\d+\.\d+\.\d+`)
	match := re.FindString(string(out))
	if match == "" {
		return "133.0.0.0"
	}
	return match
}

func pipeLogs(prefix string, r io.Reader) {
	if r == nil {
		return
	}
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		text := scanner.Text()
		if strings.Contains(text, "Failed to connect to the bus") ||
			strings.Contains(text, "org.freedesktop.DBus") ||
			strings.Contains(text, "CheckMediaAccessPermission") ||
			strings.Contains(text, "audio_manager_linux") ||
			strings.Contains(text, "bluez_dbus_manager") ||
			strings.Contains(text, "GPU stall due to ReadPixels") {
			continue
		}
		log.Println(prefix + text)
	}
}
