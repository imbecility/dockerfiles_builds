package main

import (
	_ "embed"
)

//go:embed scripts/stealth.js
var stealthJSTemplate string

//go:embed scripts/worker.js
var workerStealthJSTemplate string

//go:embed scripts/patch_console.js
var patchConsoleJS string

// stealthConfig описывает значения fingerprint'а, которые подставляются
// в stealth-скрипты, инжектируемые в страницы и воркеры.
type stealthConfig struct {
	Vendor     string
	Renderer   string
	TimerResMs float64
	Languages  string // JS-литерал массива, например `["en-US","en"]`
	Language   string
}

// RenderScripts подставляет значения fingerprint'а в шаблоны stealth-скриптов
// и возвращает готовый JS для страниц и для воркеров. Раньше это делалось
// неявно, в момент инициализации глобального блока var — теперь это явный
// шаг, вызываемый из NewProxy, когда конфигурация уже полностью собрана.
func (c stealthConfig) RenderScripts() (stealthJS, workerJS string) {
	return renderTemplate(stealthJSTemplate, c), renderTemplate(workerStealthJSTemplate, c)
}

// Config — вся конфигурация прокси верхнего уровня.
type Config struct {
	ChromeBin    string
	UpstreamHTTP string
	UpstreamWS   string
	ListenAddr   string
	PublicHost   string
	Stealth      stealthConfig
}

// LoadConfig явно читает конфигурацию из переменных окружения (с дефолтами
// на случай их отсутствия). Раньше getEnv вызывался прямо в объявлении
// глобальных var — это работало, но делало порядок инициализации и
// зависимости между переменными неочевидными. Теперь конфигурация — это
// обычное значение, которое можно собрать, передать и подменить в тестах.
func LoadConfig() *Config {
	return &Config{
		ChromeBin:    getEnv("CHROME_BIN", "/opt/headless-shell/chrome-headless-shell"),
		UpstreamHTTP: getEnv("CHROME_HTTP", "http://127.0.0.1:9222"),
		UpstreamWS:   getEnv("CHROME_WS", "ws://127.0.0.1:9222"),
		ListenAddr:   getEnv("PROXY_LISTEN", ":9223"),
		PublicHost:   getEnv("PROXY_PUBLIC_HOST", "localhost:9223"),
		Stealth: stealthConfig{
			Vendor:     "Google Inc. (NVIDIA)",
			Renderer:   "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
			TimerResMs: 0.1,
			Languages:  `["en-US","en"]`,
			Language:   "en-US",
		},
	}
}
