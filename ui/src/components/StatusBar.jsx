import React from "react";

const ERRORS = {
  adapter_unavailable: "Bluetooth is off or unavailable.",
  peripheral_unsupported: "This device can't open a room. Try connecting instead.",
  incompatible_protocol: "That device runs a different version.",
  connect_failed: "Couldn't connect to that device.",
  peer_disconnected: "The connection dropped.",
  not_connected: "You're not in a chat.",
  message_too_large: "That message is too long.",
};

export default function StatusBar({ connected, error, onDismissError }) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo">◈</span>
        BlueLink
      </div>
      <div className="conn" data-on={connected}>
        <span className="dot" />
        {connected ? "Ready" : "Reconnecting…"}
      </div>

      {error && (
        <div className="toast error" role="alert" onClick={onDismissError}>
          {ERRORS[error.code] || `Error: ${error.code}`}
          <span className="dismiss">✕</span>
        </div>
      )}
    </header>
  );
}
