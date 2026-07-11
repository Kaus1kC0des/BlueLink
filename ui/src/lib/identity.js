// Deterministic per-name visuals: a stable color + initials for avatars.

export function stripPrefix(name) {
  return (name || "").replace(/^BLK1-/, "");
}

export function displayName(name) {
  const n = stripPrefix(name).trim();
  return n || "Unnamed";
}

export function initials(name) {
  const n = displayName(name);
  const parts = n.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Hash a name to a stable hue so the same person always gets the same color.
export function hue(name) {
  const n = displayName(name);
  let h = 0;
  for (let i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) % 360;
  return h;
}

export function avatarColors(name) {
  const h = hue(name);
  return {
    bg: `hsl(${h} 62% 52%)`,
    ring: `hsl(${h} 62% 52% / 0.35)`,
  };
}

// Map RSSI (dBm) to a 0..4 signal strength for bar rendering.
export function signalLevel(rssi) {
  if (rssi == null) return 0;
  if (rssi >= -55) return 4;
  if (rssi >= -67) return 3;
  if (rssi >= -78) return 2;
  if (rssi >= -90) return 1;
  return 0;
}
