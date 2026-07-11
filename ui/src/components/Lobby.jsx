import React, { useEffect, useState } from "react";

export default function Lobby({ state, api }) {
  const [name, setName] = useState(state.status.name || "");
  const scanning = state.status.state === "scanning";
  const connecting = state.status.state === "connecting";

  // Adopt the service's persisted name once it arrives.
  useEffect(() => {
    if (state.status.name && !name) setName(state.status.name);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status.name]);

  const commitName = () => {
    const n = name.trim();
    if (n) api.setName(n);
  };

  return (
    <div className="lobby">
      <section className="card">
        <label className="field">
          <span>Your display name</span>
          <input
            value={name}
            placeholder="e.g. Priya"
            onChange={(e) => setName(e.target.value)}
            onBlur={commitName}
            onKeyDown={(e) => e.key === "Enter" && commitName()}
          />
        </label>
        <div className="actions">
          <button className="primary" onClick={api.host}>
            Host a chat
          </button>
          {scanning ? (
            <button onClick={api.stopScan}>Stop scanning</button>
          ) : (
            <button onClick={api.scan}>Scan for hosts</button>
          )}
        </div>
        <p className="hint">
          One laptop hosts; others scan and join. No pairing, no internet.
        </p>
      </section>

      {(scanning || state.peers.length > 0) && (
        <section className="card">
          <h3>Nearby hosts {scanning && <span className="spin">◌</span>}</h3>
          {state.peers.length === 0 ? (
            <p className="hint">
              {scanning ? "Looking for hosts in range…" : "No hosts found."}
            </p>
          ) : (
            <ul className="peers">
              {state.peers.map((p) => (
                <li key={p.addr}>
                  <span className="peer-name">{cleanName(p.name)}</span>
                  <span className="rssi">{signal(p.rssi)}</span>
                  <button
                    disabled={connecting}
                    onClick={() => api.join(p.addr)}
                  >
                    Join
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function cleanName(n) {
  return (n || "").replace(/^BLK1-/, "") || "(unnamed)";
}

function signal(rssi) {
  if (rssi >= -55) return "▂▄▆█";
  if (rssi >= -70) return "▂▄▆";
  if (rssi >= -85) return "▂▄";
  return "▂";
}
