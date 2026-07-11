import React, { useState } from "react";

const MAX = 4096;

export default function Composer({ onSend }) {
  const [text, setText] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const body = text.trim();
    if (!body) return;
    onSend(body);
    setText("");
  };

  return (
    <form className="composer" onSubmit={submit}>
      <input
        autoFocus
        value={text}
        maxLength={MAX}
        placeholder="Type a message…"
        onChange={(e) => setText(e.target.value)}
      />
      <button className="primary" type="submit" disabled={!text.trim()}>
        Send
      </button>
    </form>
  );
}
