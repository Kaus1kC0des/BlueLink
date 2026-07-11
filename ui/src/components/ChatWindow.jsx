import React, { useEffect, useRef } from "react";

export default function ChatWindow({ messages, members, status, onLeave }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current && endRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const title =
    status.role === "host"
      ? `Hosting${members.length ? ` · ${members.length} in room` : ""}`
      : status.host_name || "Chat";

  return (
    <div className="chatwindow">
      <div className="chat-header">
        <div>
          <strong>{title}</strong>
          {members.length > 0 && (
            <div className="members">{members.join(", ")}</div>
          )}
        </div>
        <button className="leave" onClick={onLeave}>
          {status.role === "host" ? "Stop hosting" : "Leave"}
        </button>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <p className="hint centered">No messages yet. Say hello 👋</p>
        )}
        {messages.map((m) =>
          m.system ? (
            <div key={m.key} className="msg system">
              {m.body}
            </div>
          ) : (
            <div key={m.key} className={`msg ${m.mine ? "mine" : "theirs"}`}>
              {!m.mine && <span className="sender">{m.sender}</span>}
              <span className="body">{m.body}</span>
              {m.ts && <span className="time">{fmtTime(m.ts)}</span>}
            </div>
          )
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

function fmtTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
