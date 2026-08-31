package main

import (
	"encoding/json"
	"sync"

	"github.com/gorilla/websocket"
)

// cdpRequest — команда CDP, присланная клиентом отладчика.
type cdpRequest struct {
	ID        int             `json:"id"`
	Method    string          `json:"method"`
	Params    json.RawMessage `json:"params,omitempty"`
	SessionID string          `json:"sessionId,omitempty"`
}

// cdpMessage — любое сообщение CDP (команда или событие) от апстрима.
type cdpMessage struct {
	ID        int             `json:"id,omitempty"`
	Method    string          `json:"method,omitempty"`
	Params    json.RawMessage `json:"params,omitempty"`
	SessionID string          `json:"sessionId,omitempty"`
}

// targetAttachedParams — параметры события Target.attachedToTarget,
// нужные нам только для того, чтобы понять тип таргета и его sessionId.
type targetAttachedParams struct {
	SessionID  string `json:"sessionId"`
	TargetInfo struct {
		Type string `json:"type"`
	} `json:"targetInfo"`
}

// cdpSession инкапсулирует состояние ОДНОГО соединения клиент<->Chromium:
// мьютексы записи, уже обработанные sessionId и т. п. В исходном варианте
// всё это было локальными переменными и двумя замыканиями внутри одной
// функции proxyWS — работало, но было тяжело читать и невозможно
// протестировать отдельно от HTTP-хендлера. Вынесение в структуру с
// методами делает жизненный цикл соединения явным.
type cdpSession struct {
	proxy *Proxy

	clientConn *websocket.Conn
	upConn     *websocket.Conn

	clientMu sync.Mutex
	upMu     sync.Mutex

	sessions       sync.Map // sessionId -> bool: страницам уже добавлен stealth-скрипт
	autoAttachSent sync.Map // sessionId -> bool: для сессии уже включён Target.setAutoAttach

	// internalCmds — id команд, отправленных прокси апстриму от имени этой
	// сессии, ответы на которые надо проглотить, а не пересылать клиенту.
	// Специально не на уровне Proxy: если апстрим оборвёт соединение до
	// ответа, id так и останется в мапе — а раз мапа привязана к сессии, она
	// целиком уходит под сборку мусора при закрытии соединения, а не копится
	// в общей на весь процесс мапе до его перезапуска.
	internalCmds sync.Map

	closeOnce sync.Once
}

func newCDPSession(p *Proxy, clientConn, upConn *websocket.Conn) *cdpSession {
	return &cdpSession{proxy: p, clientConn: clientConn, upConn: upConn}
}

// run запускает перекачку сообщений в обе стороны и блокируется, пока не
// закроется хотя бы одно из соединений.
func (s *cdpSession) run() {
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		defer s.close()
		s.pumpClientToUpstream()
	}()

	go func() {
		defer wg.Done()
		defer s.close()
		s.pumpUpstreamToClient()
	}()

	wg.Wait()
}

func (s *cdpSession) close() {
	s.closeOnce.Do(func() {
		_ = s.clientConn.Close()
		_ = s.upConn.Close()
	})
}

func (s *cdpSession) sendToClient(msgType int, data []byte) error {
	s.clientMu.Lock()
	defer s.clientMu.Unlock()
	return s.clientConn.WriteMessage(msgType, data)
}

func (s *cdpSession) sendToUpstream(msgType int, data []byte) error {
	s.upMu.Lock()
	defer s.upMu.Unlock()
	return s.upConn.WriteMessage(msgType, data)
}

// sendInternalCmd отправляет команду апстриму от имени прокси (не от клиента)
// и запоминает её id в internalCmds ЭТОЙ сессии, чтобы затем не пересылать ответ на неё клиенту.
func (s *cdpSession) sendInternalCmd(cmd map[string]interface{}) {
	id := s.proxy.nextInternalID()
	cmd["id"] = id
	s.internalCmds.Store(id, true)

	b, err := json.Marshal(cmd)
	if err != nil {
		return
	}

	s.upMu.Lock()
	defer s.upMu.Unlock()
	_ = s.upConn.WriteMessage(websocket.TextMessage, b)
}

// pumpClientToUpstream перегоняет сообщения от клиента отладчика в Chromium,
// перехватывая пару методов, которые не должны доходить до реального браузера.
func (s *cdpSession) pumpClientToUpstream() {
	for {
		mt, data, err := s.clientConn.ReadMessage()
		if err != nil {
			return
		}

		var req cdpRequest
		if err := json.Unmarshal(data, &req); err == nil {
			// Не даём клиенту убить браузер через Browser.close;
			// Console.enable просто подтверждаем без выполнения.
			if req.Method == "Console.enable" || req.Method == "Browser.close" {
				s.fakeAck(req)
				continue
			}
		}

		if err := s.sendToUpstream(mt, data); err != nil {
			return
		}
	}
}

// fakeAck отвечает клиенту так, будто запрос выполнен успешно, не пересылая его апстриму.
func (s *cdpSession) fakeAck(req cdpRequest) {
	resp := map[string]interface{}{"id": req.ID, "result": map[string]interface{}{}}
	if req.SessionID != "" {
		resp["sessionId"] = req.SessionID
	}
	b, err := json.Marshal(resp)
	if err != nil {
		return
	}
	_ = s.sendToClient(websocket.TextMessage, b)
}

// pumpUpstreamToClient перегоняет сообщения от Chromium клиенту, попутно
// инжектируя stealth-скрипты во вновь присоединённые страницы/воркеры и
// глотая ответы на команды, отправленные самим прокси.
func (s *cdpSession) pumpUpstreamToClient() {
	for {
		mt, data, err := s.upConn.ReadMessage()
		if err != nil {
			return
		}

		var msg cdpMessage
		if err := json.Unmarshal(data, &msg); err == nil {
			if msg.ID != 0 {
				if _, isInternal := s.internalCmds.LoadAndDelete(msg.ID); isInternal {
					continue
				}
			}

			if msg.Method == "Target.attachedToTarget" {
				s.handleAttachedToTarget(msg.Params)
			}
		}

		if err := s.sendToClient(mt, data); err != nil {
			return
		}
	}
}

// handleAttachedToTarget реагирует на присоединение нового таргета:
// страницам добавляет stealth-скрипт и включает auto-attach для дочерних
// таргетов, воркерам сразу выполняет их вариант stealth-скрипта.
func (s *cdpSession) handleAttachedToTarget(rawParams json.RawMessage) {
	var params targetAttachedParams
	if err := json.Unmarshal(rawParams, &params); err != nil {
		return
	}

	switch params.TargetInfo.Type {
	case "page", "":
		if _, loaded := s.sessions.LoadOrStore(params.SessionID, true); !loaded {
			s.sendInternalCmd(map[string]interface{}{
				"method":    "Page.addScriptToEvaluateOnNewDocument",
				"params":    map[string]string{"source": s.proxy.stealthJS},
				"sessionId": params.SessionID,
			})
		}
		if _, loaded := s.autoAttachSent.LoadOrStore(params.SessionID, true); !loaded {
			s.sendInternalCmd(map[string]interface{}{
				"method": "Target.setAutoAttach",
				"params": map[string]interface{}{
					"autoAttach":             true,
					"waitForDebuggerOnStart": false,
					"flatten":                true,
				},
				"sessionId": params.SessionID,
			})
		}

	case "worker", "shared_worker", "service_worker":
		s.sendInternalCmd(map[string]interface{}{
			"method": "Runtime.evaluate",
			"params": map[string]interface{}{
				"expression": s.proxy.workerStealthJS,
			},
			"sessionId": params.SessionID,
		})
	}
}
