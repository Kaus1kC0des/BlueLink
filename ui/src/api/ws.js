// WebSocket client for the local BlueLink service.
// Uses a relative URL so it works both under the Vite dev proxy and when the
// built UI is served by the Python service on localhost.

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

export function createWs({ onEvent, onOpen, onClose }) {
  let socket = null;
  let reconnectTimer = null;
  let closedByUser = false;

  function connect() {
    socket = new WebSocket(wsUrl());

    socket.onopen = () => onOpen && onOpen();
    socket.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data));
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = () => {
      onClose && onClose();
      if (!closedByUser) {
        reconnectTimer = setTimeout(connect, 1000); // auto-reconnect to the local service
      }
    };
    socket.onerror = () => socket && socket.close();
  }

  connect();

  return {
    send(cmd) {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(cmd));
      }
    },
    close() {
      closedByUser = true;
      clearTimeout(reconnectTimer);
      socket && socket.close();
    },
  };
}
