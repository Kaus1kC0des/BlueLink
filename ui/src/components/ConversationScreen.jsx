import React from "react";
import Avatar from "./Avatar.jsx";
import MessageList from "./MessageList.jsx";
import Composer from "./Composer.jsx";
import { displayName } from "../lib/identity.js";

export default function ConversationScreen({ state, api }) {
  const { status, members, messages } = state;
  const isHost = status.role === "host";
  const me = displayName(status.name);

  // Participants other than me (member_list includes the host's own name).
  const others = members.map(displayName).filter((n) => n !== me);
  const waiting = isHost && others.length === 0;
  const isDirect = others.length === 1;

  let title;
  let subtitle;
  if (isHost) {
    if (waiting) {
      title = "Your open room";
      subtitle = "Discoverable — waiting for people to connect";
    } else if (isDirect) {
      title = others[0];
      subtitle = "Direct chat · 1-to-1";
    } else {
      title = "Open room";
      subtitle = `${others.length} people connected`;
    }
  } else {
    title = displayName(status.host_name) || "Chat";
    subtitle = isDirect || others.length === 0 ? "Direct chat · 1-to-1" : `Open room · ${members.length} people`;
  }

  const leave = isHost ? api.stopHost : api.leave;

  // Header avatar: the other person for a 1-to-1, your own for your open room,
  // otherwise the room/host identity.
  const headerName = isDirect ? others[0] : isHost ? me : title;

  return (
    <div className="conversation">
      <div className="conv-header">
        <div className="conv-id">
          <Avatar name={headerName} size={40} />
          <div className="conv-title">
            <strong>{title}</strong>
            <span className="conv-sub">{subtitle}</span>
          </div>
        </div>
        <div className="conv-actions">
          {others.length > 1 && (
            <div className="participants" title={others.join(", ")}>
              {others.slice(0, 4).map((n) => (
                <Avatar key={n} name={n} size={26} />
              ))}
              {others.length > 4 && <span className="more">+{others.length - 4}</span>}
            </div>
          )}
          <button className="leave" onClick={leave}>
            {isHost ? "Close room" : "Leave"}
          </button>
        </div>
      </div>

      {waiting ? (
        <div className="waiting">
          <span className="radar big" data-active="true">
            <span className="ring" />
            <span className="ring" />
            <span className="glyph">◈</span>
          </span>
          <p>You're open as <strong>{me}</strong>.</p>
          <p className="muted">Ask someone nearby to open their app and Connect to you.</p>
        </div>
      ) : (
        <MessageList messages={messages} />
      )}

      <Composer onSend={api.sendMsg} disabled={waiting} />
    </div>
  );
}
