"use client";

/**
 * RSI历史记录弹窗
 * 点击币种后显示该币种的RSI历史记录
 */

import { useEffect, useState } from "react";
import { X, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { getRsiHistory, type RsiHistoryItem } from "../lib/api";

interface RsiHistoryDialogProps {
  symbol: string;
  open: boolean;
  onClose: () => void;
}

const PAGE_SIZE = 20;

export function RsiHistoryDialog({ symbol, open, onClose }: RsiHistoryDialogProps) {
  const [items, setItems] = useState<RsiHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interval, setInterval] = useState<"1d" | "4h" | "1h">("1d");

  // 加载 RSI 历史数据
  useEffect(() => {
    if (!open || !symbol) return;

    async function fetchData() {
      setIsLoading(true);
      setError(null);
      try {
        const offset = (page - 1) * PAGE_SIZE;
        const response = await getRsiHistory(symbol, interval, 200);
        if (response.error) {
          setError(response.error.message || "获取RSI历史失败");
        } else {
          // 前端分页（API返回全部数据）
          const allItems = response.data.items || [];
          setTotal(allItems.length);
          setItems(allItems.slice(offset, offset + PAGE_SIZE));
        }
      } catch {
        setError("网络请求失败");
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [symbol, open, page, interval]);

  // 重置分页
  useEffect(() => {
    if (open) {
      setPage(1);
    }
  }, [open, symbol, interval]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const getStateColor = (state: string) => {
    switch (state) {
      case "overbought":
        return "text-red-500";
      case "oversold":
        return "text-green-500";
      default:
        return "text-[var(--terminal-muted)]";
    }
  };

  const getStateLabel = (state: string) => {
    switch (state) {
      case "overbought":
        return "🔥 超买";
      case "oversold":
        return "💚 超卖";
      default:
        return "○ 中性";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      {/* 遮罩 */}
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        aria-label="关闭弹窗遮罩"
        onClick={onClose}
      />

      {/* 弹窗内容 */}
      <div className="relative z-10 flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)] shadow-2xl">
        {/* 头部 */}
        <div className="flex items-center justify-between border-b border-[var(--terminal-border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <h4 className="text-lg font-bold text-[var(--terminal-text)]">
              {symbol.replace("USDT", "")} RSI 历史
            </h4>
            <div className="flex gap-1">
              {(["1d", "4h", "1h"] as const).map((int) => (
                <button
                  key={int}
                  onClick={() => setInterval(int)}
                  className={`px-2 py-1 text-xs rounded ${
                    interval === int
                      ? "bg-[var(--terminal-cyan)] text-black"
                      : "text-[var(--terminal-muted)] hover:text-[var(--terminal-text)]"
                  }`}
                >
                  {int.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex items-center gap-1 text-[var(--terminal-muted)] hover:text-[var(--terminal-text)] text-sm"
          >
            <X className="w-4 h-4" />
            关闭
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-[var(--terminal-cyan)]" />
              <span className="ml-2 text-[var(--terminal-muted)]">加载中...</span>
            </div>
          ) : error ? (
            <div className="text-red-500 text-center py-8">{error}</div>
          ) : items.length === 0 ? (
            <div className="text-[var(--terminal-muted)] text-center py-8">暂无数据</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[var(--terminal-muted)] border-b border-[var(--terminal-border)]">
                  <th className="text-left py-2 font-normal">时间</th>
                  <th className="text-right py-2 font-normal">RSI</th>
                  <th className="text-right py-2 font-normal">状态</th>
                  <th className="text-right py-2 font-normal">收盘价</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr
                    key={`${item.timestamp}-${idx}`}
                    className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-border)]/20"
                  >
                    <td className="py-2 text-[var(--terminal-text)]">{item.time}</td>
                    <td className={`py-2 text-right font-mono ${getStateColor(item.state)}`}>
                      {item.rsi_value}
                    </td>
                    <td className="py-2 text-right text-[var(--terminal-muted)]">
                      {getStateLabel(item.state)}
                    </td>
                    <td className="py-2 text-right font-mono text-[var(--terminal-text)]">
                      ${item.close_price}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 分页 */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-[var(--terminal-border)] px-4 py-3">
            <div className="text-xs text-[var(--terminal-muted)]">
              共 {total} 条记录，第 {page}/{totalPages} 页
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex items-center gap-1 px-3 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--terminal-cyan)]"
              >
                <ChevronLeft className="w-4 h-4" />
                上一页
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="flex items-center gap-1 px-3 py-1 text-xs rounded border border-[var(--terminal-border)] disabled:opacity-50 disabled:cursor-not-allowed hover:border-[var(--terminal-cyan)]"
              >
                下一页
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
