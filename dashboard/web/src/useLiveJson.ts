import { useEffect, useRef, useState } from "react";

// Fetch JSON again whenever `trigger` changes, with at most one request in flight.
// Changes during a request cause exactly one follow-up; the last result stays shown.
export function useLiveJson<T>(url: string | null, trigger: unknown): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const pending = useRef(false);
  const current = useRef(url);
  current.current = url;

  useEffect(() => { setData(null); setError(null); }, [url]);

  useEffect(() => {
    if (!url) return;
    const load = () => {
      if (inFlight.current) { pending.current = true; return; }
      inFlight.current = true;
      const requested = current.current;
      if (!requested) { inFlight.current = false; return; }
      fetch(requested)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((d: T) => { if (requested === current.current) { setData(d); setError(null); } })
        .catch((e: Error) => setError(e.message))
        .finally(() => {
          inFlight.current = false;
          if (pending.current || requested !== current.current) { pending.current = false; load(); }
        });
    };
    load();
  }, [url, trigger]);

  return { data, error };
}
