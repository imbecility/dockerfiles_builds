package main

import (
	"fmt"
	"os"
	"strings"
)

// getEnv возвращает значение переменной окружения key, либо def, если она не задана.
func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// renderTemplate подставляет плейсхолдеры вида __VENDOR__ в tpl значениями из c.
func renderTemplate(tpl string, c stealthConfig) string {
	r := strings.NewReplacer(
		"__VENDOR__", c.Vendor,
		"__RENDERER__", c.Renderer,
		"__TIMER_RES__", fmt.Sprintf("%v", c.TimerResMs),
		"__LANGUAGES__", c.Languages,
		"__LANGUAGE__", c.Language,
		"__PATCH_CONSOLE__", patchConsoleJS,
	)
	return r.Replace(tpl)
}
