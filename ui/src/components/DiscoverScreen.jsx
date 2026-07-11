import React, { useEffect, useState } from "react";
import Avatar from "./Avatar.jsx";
import DeviceCard from "./DeviceCard.jsx";
import { displayName } from "../lib/identity.js";

export default function DiscoverScreen({ state, api, connected }) {
  const { status, peers } = state;
  const scanning = status.state === "scanning";
  const connecting = status.state === "connecting";
  const [name, setName] = useState(displayName(status.name));
  const [editing, setEditing] = useState(!status.name);
  const [joiningAddr, setJoiningAddr] = useState(null);

  // Keep scanning whenever we're sitting idle on this screen — a live radar.
  useEffect(() => {
    if (connected && status.state === "idle") api.scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, status.state]);

  // Adopt the persisted name once the service reports it.
  useEffect(() => {
    if (status.name && editing === false) setName(displayName(status.name));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.name]);

  // Clear the per-card connecting state if a join attempt falls back to idle.
  useEffect(() => {
    if (status.state !== "connecting") setJoiningAddr(null);
  }, [status.state]);

  const commitName = () => {
    const n = name.trim();
    if (n) {
      api.setName(n);
      setEditing(false);
    }
  };

  const join = (addr) => {
    setJoiningAddr(addr);
    api.join(addr);
  };

  return (
    <div className="discover">
      <div className="discover-hero">
        <div className="you">
          <Avatar name={name} size={56} ring />
          {editing ? (
            <div className="name-edit">
              <input
                autoFocus
                value={name}
                placeholder="Your name"
                maxLength={32}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && commitName()}
              />
              <button className="ghost" onClick={commitName}>
                Save
              </button>
            </div>
          ) : (
            <button className="name-chip" onClick={() => setEditing(true)}>
              {displayName(name)} <span className="edit-hint">edit</span>
            </button>
          )}
        </div>

        <button className="open-cta" onClick={api.host} disabled={!connected}>
          <span className="radar" data-active="true">
            <span className="ring" />
            <span className="ring" />
            <span className="glyph">◈</span>
          </span>
          <span className="open-cta-text">
            <strong>Open to all</strong>
            <small>Anyone nearby can connect and chat with you</small>
          </span>
        </button>
      </div>

      <div className="nearby">
        <div className="nearby-head">
          <h3>
            Nearby
            {scanning && <span className="live-dot" title="Scanning" />}
          </h3>
          <button
            className="ghost small"
            onClick={scanning ? api.stopScan : api.scan}
            disabled={!connected}
          >
            {scanning ? "Pause" : "Scan"}
          </button>
        </div>

        {peers.length === 0 ? (
          <div className="empty">
            <span className="radar big" data-active={scanning}>
              <span className="ring" />
              <span className="ring" />
              <span className="glyph">◌</span>
            </span>
            <p>
              {scanning
                ? "Looking for open devices in range…"
                : "No devices found yet."}
            </p>
            <p className="muted">
              Connect to someone for a private 1-to-1, or go{" "}
              <strong>Open to all</strong> so others can find you.
            </p>
          </div>
        ) : (
          <div className="device-grid">
            {peers.map((p) => (
              <DeviceCard
                key={p.addr}
                peer={p}
                connecting={joiningAddr === p.addr}
                disabled={connecting}
                onConnect={() => join(p.addr)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
