import React, { useEffect, useMemo, useReducer, useRef } from "react";
import { createWs } from "./api/ws.js";
import { initialState, reducer } from "./state/store.js";
import StatusBar from "./components/StatusBar.jsx";
import Lobby from "./components/Lobby.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import Composer from "./components/Composer.jsx";

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = createWs({
      onEvent: (event) => dispatch({ type: "event", event }),
      onOpen: () => dispatch({ type: "ws_open" }),
      onClose: () => dispatch({ type: "ws_close" }),
    });
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const send = (cmd) => wsRef.current && wsRef.current.send(cmd);

  const { role, state: connState } = state.status;
  const inChat =
    role === "host" || (role === "member" && connState === "connected");

  // Clear the transcript when a fresh session starts.
  const prevInChat = useRef(false);
  useEffect(() => {
    if (inChat && !prevInChat.current) dispatch({ type: "reset_messages" });
    prevInChat.current = inChat;
  }, [inChat]);

  const api = useMemo(
    () => ({
      setName: (name) => send({ t: "set_name", name }),
      host: () => send({ t: "host" }),
      stopHost: () => send({ t: "stop_host" }),
      scan: () => send({ t: "scan" }),
      stopScan: () => send({ t: "stop_scan" }),
      join: (addr) => send({ t: "join", addr }),
      leave: () => send({ t: "leave" }),
      sendMsg: (body) => send({ t: "send", body }),
    }),
    []
  );

  return (
    <div className="app">
      <StatusBar
        status={state.status}
        connected={state.connected}
        error={state.error}
        onDismissError={() => dispatch({ type: "dismiss_error" })}
      />
      {inChat ? (
        <div className="chat">
          <ChatWindow
            messages={state.messages}
            members={state.members}
            status={state.status}
            onLeave={role === "host" ? api.stopHost : api.leave}
          />
          <Composer onSend={api.sendMsg} />
        </div>
      ) : (
        <Lobby state={state} api={api} />
      )}
    </div>
  );
}
