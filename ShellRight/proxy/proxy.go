package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"

	"github.com/gorilla/websocket"
)

// Proxy — CDP-прокси между клиентом отладчика и реальным Chromium:
// подменяет пару опасных методов и инжектирует stealth-скрипты в новые
// страницы и воркеры. Раньше это состояние (адреса апстрима, счётчик
// внутренних команд, карта их id) было раскидано по глобальным var в
// config.go и main.go — теперь это поля одной структуры с явным
// конструктором, что делает возможным, например, поднять несколько
// независимых прокси с разной конфигурацией в одном процессе (в тестах).
type Proxy struct {
	// internalCmdCounter обязан оставаться первым полем: пакет sync/atomic
	// гарантирует 64-битное выравнивание только для первого слова
	// аллоцированной структуры, что важно для atomic-операций на 32-битных
	// платформах. Общий на все сессии — это просто монотонный счётчик, не
	// накапливает данные, поэтому ему ничего не грозит в отличие от карты
	// internalCmds (см. cdpSession): она теперь живёт per-connection, чтобы
	// id команд, на которые апстрим так и не ответил, не оседали в общей
	// на весь процесс мапе.
	internalCmdCounter atomic.Int64

	upstreamHTTP string
	upstreamWS   string
	listenAddr   string
	publicHost   string

	stealthJS       string
	workerStealthJS string
}

// NewProxy собирает Proxy из конфигурации, рендеря stealth-скрипты один раз
// заранее (а не при каждом новом подключении).
func NewProxy(cfg *Config) *Proxy {
	stealthJS, workerJS := cfg.Stealth.RenderScripts()
	p := &Proxy{
		upstreamHTTP:    cfg.UpstreamHTTP,
		upstreamWS:      cfg.UpstreamWS,
		listenAddr:      cfg.ListenAddr,
		publicHost:      cfg.PublicHost,
		stealthJS:       stealthJS,
		workerStealthJS: workerJS,
	}
	p.internalCmdCounter.Store(8000000)

	return p
}

// Handler возвращает HTTP-хендлер со всеми маршрутами прокси. Вынесен
// отдельно от ListenAndServe, чтобы его можно было смонтировать в тестовый
// httptest.Server без реального сетевого порта.
func (p *Proxy) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/devtools/", p.proxyWS)
	mux.HandleFunc("/", p.proxyHTTP)
	return mux
}

// ListenAndServe запускает HTTP-сервер прокси на p.listenAddr.
func (p *Proxy) ListenAndServe() error {
	log.Printf("[CDP-Proxy] Running on %s (upstream: %s)", p.listenAddr, p.upstreamHTTP)
	return http.ListenAndServe(p.listenAddr, p.Handler())
}

func (p *Proxy) nextInternalID() int {
	return int(p.internalCmdCounter.Add(1))
}

func (p *Proxy) getUpstreamHost() string {
	u, err := url.Parse(p.upstreamWS)
	if err != nil {
		return "127.0.0.1:9222"
	}
	return u.Host
}

// rewriteBody подменяет в JSON-ответах Chromium (например, /json/list) хост
// апстрима на тот, по которому реально достучались до прокси.
func (p *Proxy) rewriteBody(body []byte, reqHost string) []byte {
	targetHost := p.publicHost
	if reqHost != "" && (p.publicHost == "localhost:9223" || p.publicHost == ":9223") {
		targetHost = reqHost
	}
	s := string(body)
	s = strings.ReplaceAll(s, p.getUpstreamHost(), targetHost)
	return []byte(s)
}

func (p *Proxy) proxyHTTP(w http.ResponseWriter, r *http.Request) {
	if websocket.IsWebSocketUpgrade(r) {
		p.proxyWS(w, r)
		return
	}

	targetURL := p.upstreamHTTP + r.URL.RequestURI()
	req, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	for k, vv := range r.Header {
		for _, v := range vv {
			req.Header.Add(k, v)
		}
	}
	req.Host = p.getUpstreamHost()

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		http.Error(w, fmt.Sprintf("Upstream unreachable: %v", err), http.StatusBadGateway)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	contentType := resp.Header.Get("Content-Type")
	if strings.Contains(contentType, "json") || strings.HasPrefix(r.URL.Path, "/json") {
		body = p.rewriteBody(body, r.Host)
	}

	for k, vv := range resp.Header {
		if strings.EqualFold(k, "Content-Length") {
			continue
		}
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}
	w.Header().Set("Content-Length", fmt.Sprintf("%d", len(body)))
	w.WriteHeader(resp.StatusCode)
	_, _ = w.Write(body)
}

// upgrader.CheckOrigin принимает WS-апгрейд с любого origin
var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// proxyWS поднимает WS-соединение к апстриму и запускает cdpSession,
// которая владеет всем состоянием, специфичным для этого соединения.
func (p *Proxy) proxyWS(w http.ResponseWriter, r *http.Request) {
	clientConn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer func() { _ = clientConn.Close() }()

	upURL := p.upstreamWS + r.URL.RequestURI()
	upConn, _, err := websocket.DefaultDialer.Dial(upURL, nil)
	if err != nil {
		log.Printf("[WS] Upstream dial failed to %s: %v", upURL, err)
		_ = clientConn.WriteMessage(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseProtocolError, "Upstream unavailable"),
		)
		return
	}
	defer func() { _ = upConn.Close() }()

	newCDPSession(p, clientConn, upConn).run()
}
