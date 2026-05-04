"use client";

/**
 * WebSocket Context - 提供实时状态推送连接管理。
 *
 * 当连接成功时，组件通过订阅通道接收推送；
 * 当连接失败时，自动降级为 HTTP 轮询。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

// WebSocket 连接状态类型
type WebSocketStatus = "connecting" | "connected" | "disconnected" | "error";

// 推送消息类型
type WebSocketMessage = {
  channel: string;
  type?: string;
  timestamp: string;
  data: unknown;
};

// Context 值类型
type WebSocketContextValue = {
  status: WebSocketStatus;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  lastMessage: WebSocketMessage | null;
  channelMessages: Record<string, WebSocketMessage>;
  reconnect: () => void;
};

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// WebSocket URL 配置
function getWebSocketUrl(): string {
  if (typeof window === "undefined") return "";

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

  // 后端 API WebSocket 端点在端口 9011，路径是 /ws（无 prefix）
  // 生产环境：使用 NEXT_PUBLIC_API_URL 或默认端口
  // 开发环境：直接连接 localhost:9011
  const apiPort = process.env.NEXT_PUBLIC_API_PORT || "9011";
  const apiHost = process.env.NEXT_PUBLIC_API_HOST || window.location.hostname;
  const wsHost = `${apiHost}:${apiPort}`;

  // 从 cookie 获取认证 token
  const token = getAuthToken();

  // 构建带 token 的 URL
  const baseUrl = `${protocol}//${wsHost}/api/v1/ws`;
  return token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
}

// 从 cookie 获取认证 token
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;

  // 从 cookie 中读取 quant_admin_token
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "quant_admin_token" && value) {
      return value;
    }
  }
  return null;
}

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<WebSocketStatus>("connecting");
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [channelMessages, setChannelMessages] = useState<Record<string, WebSocketMessage>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const subscriptionsRef = useRef<Set<string>>(new Set());
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);

  const connect = useCallback(() => {
    const url = getWebSocketUrl();
    if (!url) return;

    setStatus("connecting");

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        reconnectAttemptsRef.current = 0;

        // 重新订阅之前的通道
        subscriptionsRef.current.forEach((channel) => {
          ws.send(JSON.stringify({ type: "subscribe", channel }));
        });
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);

          if (message.channel) {
            setChannelMessages((prev) => ({
              ...prev,
              [message.channel]: message,
            }));
          }
        } catch {
          // 忽略解析错误（如 pong 响应）
        }
      };

      ws.onerror = () => {
        setStatus("error");
      };

      ws.onclose = () => {
        setStatus("disconnected");
        wsRef.current = null;

        // 自动重连（指数退避）
        if (reconnectAttemptsRef.current < 10) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptsRef.current),
            30000
          );
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            connect();
          }, delay);
        }
      };
    } catch {
      setStatus("error");
    }
  }, []);

  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
    }
    connect();
  }, [connect]);

  const subscribe = useCallback((channel: string) => {
    subscriptionsRef.current.add(channel);

    if (wsRef.current && status === "connected") {
      wsRef.current.send(JSON.stringify({ type: "subscribe", channel }));
    }
  }, [status]);

  const unsubscribe = useCallback((channel: string) => {
    subscriptionsRef.current.delete(channel);

    if (wsRef.current && status === "connected") {
      wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
    }
  }, [status]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  // 定期发送心跳
  useEffect(() => {
    if (status !== "connected") return;

    const interval = window.setInterval(() => {
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 15000);

    return () => window.clearInterval(interval);
  }, [status]);

  const value: WebSocketContextValue = {
    status,
    subscribe,
    unsubscribe,
    lastMessage,
    channelMessages,
    reconnect,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}

export function useWebSocketStatus(): WebSocketStatus {
  const context = useContext(WebSocketContext);
  return context?.status ?? "disconnected";
}