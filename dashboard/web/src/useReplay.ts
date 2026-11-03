import { useCallback, useEffect, useRef, useState } from "react";
import type { Connection, Meta, ReplayStatus, Snapshot, TradingEvent } from "./types";

const FEED_LIMIT = 300;
const SILENCE_MS = 5000; // the server sends replay status about twice a second

export interface ReplayState {
  meta: Meta | null;
  metaError: string | null;
  snapshot: Snapshot | null;
  status: ReplayStatus | null;
  events: TradingEvent[];          // non-bar events, newest last, de-duplicated by event_id
  connection: Connection;
  lastMessageAt: number | null;
  uiDuplicatesIgnored: number;
  modeRejected: number;
  control: (action: string, speed?: number) => Promise<void>;
  controlError: string | null;
  retry: () => void;
}

export function useReplay(): ReplayState {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [events, setEvents] = useState<TradingEvent[]>([]);
  const [connection, setConnection] = useState<Connection>("connecting");
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [uiDuplicatesIgnored, setDup] = useState(0);
  const [modeRejected, setModeRejected] = useState(0);
  const [controlError, setControlError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const seen = useRef(new Set<string>());

  useEffect(() => {
    let cancelled = false;
    setMetaError(null);
    fetch("/api/meta")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((m: Meta) => !cancelled && setMeta(m))
      .catch((e: Error) => !cancelled && setMetaError(e.message));
    return () => { cancelled = true; };
  }, [attempt]);

  useEffect(() => {
    if (!meta) return;
    const source = new EventSource("/api/stream");
    const touch = () => setLastMessageAt(Date.now());
    source.onopen = () => setConnection("connected");
    source.onerror = () =>
      setConnection(source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting");
    source.addEventListener("reset", () => {
      touch();
      seen.current = new Set();
      setEvents([]);
      setDup(0);
    });
    source.addEventListener("ev", (msg) => {
      touch();
      const ev = JSON.parse((msg as MessageEvent).data) as TradingEvent;
      if (ev.mode !== meta.mode) {      // never mix modes silently
        setModeRejected((n) => n + 1);
        return;
      }
      if (seen.current.has(ev.event_id)) {
        setDup((n) => n + 1);
        return;
      }
      seen.current.add(ev.event_id);
      if (ev.type !== "bar") setEvents((prev) => [...prev.slice(-(FEED_LIMIT - 1)), ev]);
    });
    source.addEventListener("snapshot", (msg) => {
      touch();
      setSnapshot(JSON.parse((msg as MessageEvent).data) as Snapshot);
    });
    source.addEventListener("replay", (msg) => {
      touch();
      setConnection("connected");
      setStatus(JSON.parse((msg as MessageEvent).data) as ReplayStatus);
    });
    return () => source.close();
  }, [meta]);

  // Detect a silent connection: open socket but no messages.
  useEffect(() => {
    const id = setInterval(() => {
      if (lastMessageAt && Date.now() - lastMessageAt > SILENCE_MS && connection === "connected") {
        setConnection("reconnecting");
      }
    }, 1000);
    return () => clearInterval(id);
  }, [lastMessageAt, connection]);

  const control = useCallback(async (action: string, speed?: number) => {
    setControlError(null);
    try {
      const r = await fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dashboard-Control": "1" },
        body: JSON.stringify({ action, speed }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setStatus((await r.json()) as ReplayStatus);
    } catch (e) {
      setControlError(`Control "${action}" failed: ${(e as Error).message}`);
    }
  }, []);

  return {
    meta, metaError, snapshot, status, events, connection, lastMessageAt,
    uiDuplicatesIgnored, modeRejected, control, controlError,
    retry: () => setAttempt((n) => n + 1),
  };
}
