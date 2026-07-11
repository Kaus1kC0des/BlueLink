// UI state reducer. Mirrors the service event schema (see LLD.md section 5.2).

export const initialState = {
  connected: false, // WebSocket to the local service is open
  status: { role: "idle", state: "idle", host_name: null, name: "" },
  peers: [], // [{addr, name, rssi}]
  members: [], // [name]
  messages: [], // [{key, id, sender, ts, body, mine, system}]
  error: null, // {code, detail} last error, for a dismissible banner
};

let msgKey = 0;

export function reducer(state, action) {
  const ev = action.event;
  switch (action.type) {
    case "ws_open":
      return { ...state, connected: true };
    case "ws_close":
      return { ...state, connected: false };
    case "reset_messages":
      return { ...state, messages: [], members: [] };
    case "dismiss_error":
      return { ...state, error: null };
    case "event":
      return applyEvent(state, ev);
    default:
      return state;
  }
}

function applyEvent(state, ev) {
  switch (ev.t) {
    case "status":
      return { ...state, status: ev };
    case "peers":
      return { ...state, peers: ev.peers || [] };
    case "member_list":
      return { ...state, members: ev.members || [] };
    case "message":
      return {
        ...state,
        messages: [...state.messages, { ...ev, key: ++msgKey }],
      };
    case "sent":
      return state; // delivery hook; message already shown optimistically
    case "error":
      return { ...state, error: { code: ev.code, detail: ev.detail } };
    default:
      return state;
  }
}
