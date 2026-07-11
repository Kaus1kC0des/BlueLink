import React from "react";
import { avatarColors, initials } from "../lib/identity.js";

export default function Avatar({ name, size = 36, ring = false }) {
  const { bg, ring: ringColor } = avatarColors(name);
  return (
    <span
      className="avatar"
      style={{
        width: size,
        height: size,
        background: bg,
        fontSize: size * 0.4,
        boxShadow: ring ? `0 0 0 4px ${ringColor}` : "none",
      }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
