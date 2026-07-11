import React from "react";
import { signalLevel } from "../lib/identity.js";

export default function Signal({ rssi }) {
  const level = signalLevel(rssi);
  return (
    <span className="signal" title={rssi != null ? `${rssi} dBm` : "unknown"}>
      {[1, 2, 3, 4].map((i) => (
        <span key={i} className="bar" data-on={i <= level} style={{ height: 3 + i * 3 }} />
      ))}
    </span>
  );
}
