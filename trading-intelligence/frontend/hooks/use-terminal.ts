"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API, api, getSession, type State } from "@/lib/api";

export function useTerminal() {
  const client = useQueryClient();
  const [connected, setConnected] = useState(false);
  const query = useQuery({ queryKey: ["state"], queryFn: () => api<State>("state"), retry: 1, refetchOnWindowFocus: false });
  useEffect(() => {
    let stopped = false, socket: WebSocket | undefined, timer: ReturnType<typeof setTimeout>, watchdog: ReturnType<typeof setTimeout>, attempt = 0;
    const schedule = () => { if (!stopped) timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempt++) + Math.random() * 500); };
    const connect = async () => {
      try {
        const csrf = await getSession();
        if (stopped) return;
        socket = new WebSocket(API.replace(/^http/, "ws") + "/ws");
        socket.onopen = () => socket?.send(JSON.stringify({ csrf }));
        socket.onmessage = event => {
          const state = JSON.parse(event.data) as State;
          client.setQueryData(["state"], state); setConnected(true); attempt = 0;
          clearTimeout(watchdog); watchdog = setTimeout(() => { setConnected(false); socket?.close(); }, 10000);
        };
        socket.onerror = () => socket?.close();
        socket.onclose = () => { setConnected(false); schedule(); };
      } catch { setConnected(false); schedule(); }
    };
    void connect();
    return () => { stopped = true; clearTimeout(timer); clearTimeout(watchdog); socket?.close(); };
  }, [client]);
  return { ...query, connected };
}
