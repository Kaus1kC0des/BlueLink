import React, { useRef, useState } from "react";

const MAX = 4096;

export default function Composer({ onSend, disabled }) {
  const [text, setText] = useState("");
  const ref = useRef(null);

  const submit = () => {
    const body = text.trim();
    if (!body) return;
    onSend(body);
    setText("");
    if (ref.current) ref.current.style.height = "auto";
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onInput = (e) => {
    setText(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  return (
    <div className="composer">
      <textarea
        ref={ref}
        rows={1}
        value={text}
        maxLength={MAX}
        disabled={disabled}
        placeholder={disabled ? "Waiting for someone to connect…" : "Type a message…"}
        onChange={onInput}
        onKeyDown={onKeyDown}
      />
      <button
        className="send"
        onClick={submit}
        disabled={disabled || !text.trim()}
        aria-label="Send"
      >
        ➤
      </button>
    </div>
  );
}
