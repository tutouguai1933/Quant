"use client";

/**
 * RSI 数据共享上下文
 * 避免 EntryStatusCard 和 RsiSummaryCard 重复请求 RSI 数据
 */

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getRsiSummary, type RsiSummaryItem } from "../lib/api";

type RsiDataContextValue = {
  items: RsiSummaryItem[];
  isLoading: boolean;
  error: string | null;
  lastUpdate: string;
  refresh: () => void;
};

const RsiDataContext = createContext<RsiDataContextValue | null>(null);

export function RsiDataProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<RsiSummaryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>("");

  const fetchData = useCallback(async () => {
    try {
      const response = await getRsiSummary("1d");
      if (response.error) {
        setError(response.error.message || "获取RSI数据失败");
      } else {
        setItems(response.data.items || []);
        setLastUpdate(new Date().toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai" }));
        setError(null);
      }
    } catch {
      setError("网络请求失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // 每5分钟刷新一次
    const interval = setInterval(fetchData, 300000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <RsiDataContext.Provider value={{ items, isLoading, error, lastUpdate, refresh: fetchData }}>
      {children}
    </RsiDataContext.Provider>
  );
}

export function useRsiData(): RsiDataContextValue {
  const context = useContext(RsiDataContext);
  if (!context) {
    // 如果没有 Provider，返回默认值并自动获取数据（向后兼容）
    return {
      items: [],
      isLoading: true,
      error: null,
      lastUpdate: "",
      refresh: () => {},
    };
  }
  return context;
}
