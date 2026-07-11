import React, { useEffect, useRef } from "react";
import Avatar from "./Avatar.jsx";
import { displayName } from "../lib/identity.js";

export default function MessageList({ messages }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const rows = groupMessages(messages);

  return (
    <div className="messages">
      {messages.length === 0 && (
        <div className="chat-empty">
          <span className="wave">👋</span>
          <p>No messages yet — say hello.</p>
        </div>
      )}
      {rows.map((row) =>
        row.system ? (
          <div key={row.key} className="sys-pill">
            {row.body}
          </div>
        ) : (
          <div key={row.key} className={`bubble-row ${row.mine ? "mine" : "theirs"}`}>
            {!row.mine && <Avatar name={row.sender} size={30} />}
            <div className="bubble-stack">
              {!row.mine && <span className="bubble-sender">{displayName(row.sender)}</span>}
              {row.items.map((m) => (
                <div key={m.key} className="bubble">
                  <span className="bubble-body">{m.body}</span>
                  {m.ts && <span className="bubble-time">{fmtTime(m.ts)}</span>}
                </div>
              ))}
            </div>
          </div>
        )
      )}
      <div ref={endRef} />
    </div>
  );
}

// Group consecutive same-sender messages so the avatar/name show once per run.
function groupMessages(messages) {
  const rows = [];
  for (const m of messages) {
    if (m.system) {
      rows.push({ key: `s${m.key}`, system: true, body: m.body });
      continue;
    }
    const last = rows[rows.length - 1];
    if (last && !last.system && last.mine === m.mine && last.sender === m.sender) {
      last.items.push(m);
    } else {
      rows.push({
        key: `g${m.key}`,
        system: false,
        mine: m.mine,
        sender: m.sender,
        items: [m],
      });
    }
  }
  return rows;
}

function fmtTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}
