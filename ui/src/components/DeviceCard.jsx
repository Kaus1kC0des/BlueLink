import React from "react";
import Avatar from "./Avatar.jsx";
import Signal from "./Signal.jsx";
import { displayName } from "../lib/identity.js";

export default function DeviceCard({ peer, connecting, disabled, onConnect }) {
  return (
    <button
      className="device-card"
      onClick={onConnect}
      disabled={disabled}
      data-connecting={connecting}
    >
      <Avatar name={peer.name} size={44} />
      <span className="device-info">
        <span className="device-name">{displayName(peer.name)}</span>
        <span className="device-sub">
          <span className="open-tag">Open</span>
          <Signal rssi={peer.rssi} />
        </span>
      </span>
      <span className="device-action">
        {connecting ? <span className="spinner" /> : "Connect"}
      </span>
    </button>
  );
}
