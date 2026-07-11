import React from "react";

const STATE_LABEL = {
  idle: "Idle",
  advertising: "Hosting — waiting for peers",
  hosting: "Hosting",
  scanning: "Scanning…",
  connecting: "Connecting…",
  connected: "Connected",
};

export default function StatusBar({ status, connected, error, onDismissError }) {
  return (
    <header className="statusbar">
      <div className="brand">
        <span className="dot" data-on={connected} />
        BlueLink
      </div>
      <div className="status-mid">
        {status.role === "member" && status.host_name
          ? `In: ${status.host_name}`
          : STATE_LABEL[status.state] || status.state}
      </div>
      <div className="me">{status.name ? `You: ${status.name}` : ""}</div>
      {!connected && (
        <div className="banner warn">Service offline — reconnecting…</div>
      )}
      {error && (
        <div className="banner error" onClick={onDismissError} title="Dismiss">
          {friendlyError(error)} ✕
        </div>
      )}
    </header>
  );
}

function friendlyError(e) {
  const map = {
    adapter_unavailable: "Bluetooth is off or unavailable.",
    peripheral_unsupported: "This adapter can't host. Try joining instead.",
    incompatible_protocol: "That peer runs a different BlueLink version.",
    connect_failed: "Couldn't connect to that peer.",
    peer_disconnected: "The connection dropped.",
    not_connected: "You're not in a chat.",
    message_too_large: "Message is too long.",
  };
  return map[e.code] || `Error: ${e.code}${e.detail ? ` (${e.detail})` : ""}`;
}
