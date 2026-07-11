import React, { useEffect, useMemo, useReducer, useRef } from "react";
import { createWs } from "./api/ws.js";
import { initialState, reducer } from "./state/store.js";
import StatusBar from "./components/StatusBar.jsx";
import DiscoverScreen from "./components/DiscoverScreen.jsx";
import ConversationScreen from "./components/ConversationScreen.jsx";

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

  const send = (cmd) => wsRef.current?.send(cmd);

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

  const { role, state: connState } = state.status;
  const inChat = role === "host" || (role === "member" && connState === "connected");

  // Clear the transcript when a fresh conversation starts.
  const prevInChat = useRef(false);
  useEffect(() => {
    if (inChat && !prevInChat.current) dispatch({ type: "reset_messages" });
    prevInChat.current = inChat;
  }, [inChat]);

  return (
    <div className="app">
      <StatusBar
        connected={state.connected}
        error={state.error}
        onDismissError={() => dispatch({ type: "dismiss_error" })}
      />
      {inChat ? (
        <ConversationScreen state={state} api={api} />
      ) : (
        <DiscoverScreen state={state} api={api} connected={state.connected} />
      )}
    </div>
  );
}
