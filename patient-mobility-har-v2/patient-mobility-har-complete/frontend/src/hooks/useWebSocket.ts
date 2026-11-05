import * as React from "react";

export interface LiveMessage {
  activity_label: string | null;
  confidence: number;
  skeleton_points: [number, number][];
  fps: number;
  fall_detected: boolean;
  inactivity_warning: boolean;
  camera_connected: boolean;
  updated_at: string | null;
  frame_jpeg_base64: string | null;
}

const RECONNECT_DELAY_MS = 2000;

export function useWebSocket(enabled: boolean = true) {
  const [lastMessage, setLastMessage] = React.useState<LiveMessage | null>(null);
  const [isConnected, setIsConnected] = React.useState(false);
  const socketRef = React.useRef<WebSocket | null>(null);
  const reconnectTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!enabled) return;

    let isUnmounted = false;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
      socketRef.current = socket;

      socket.onopen = () => setIsConnected(true);

      socket.onmessage = (event) => {
        try {
          const parsed: LiveMessage = JSON.parse(event.data);
          setLastMessage(parsed);
        } catch {
          // Ignore malformed frames rather than crashing the live view.
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        if (!isUnmounted) {
          reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      socketRef.current?.close();
    };
  }, [enabled]);

  return { lastMessage, isConnected };
}
