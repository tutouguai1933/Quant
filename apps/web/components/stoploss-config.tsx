"use client";

import { useCallback, useEffect, useState } from "react";
import { Shield, TrendingUp, TrendingDown, RefreshCw, AlertTriangle, CheckCircle2, Settings } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type StoplossConfig = {
  base_stoploss: string;
  min_stoploss: string;
  max_stoploss: string;
  high_volatility_threshold: string;
  low_volatility_threshold: string;
  adjustment_interval_minutes: number;
  throttle_min_change_pct: string;
};

type PositionState = {
  symbol: string;
  position_id: string;
  current_stoploss: string;
  entry_price: string;
  current_price: string;
  volatility_factor: string;
  last_adjusted_at: string;
  adjustment_count: number;
};

type VolatilityData = {
  symbol: string;
  atr: string;
  atr_percent: string;
  std: string;
  std_percent: string;
  volatility_factor: string;
  calculated_at: string;
  period_atr: number;
  period_std: number;
  data_points: number;
};

type StoplossAdjustment = {
  symbol: string;
  previous_stoploss: string;
  new_stoploss: string;
  volatility_factor: string;
  reason: string;
  adjusted_at: string;
  success: boolean;
};

export function StoplossConfigCard() {
  const [config, setConfig] = useState<StoplossConfig | null>(null);
  const [positions, setPositions] = useState<PositionState[]>([]);
  const [editing, setEditing] = useState(false);
  const [editValues, setEditValues] = useState<Partial<StoplossConfig>>({});
  const [loading, setLoading] = useState(false);
  const [adjusting, setAdjusting] = useState(false);
  const [lastAdjustment, setLastAdjustment] = useState<StoplossAdjustment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/stoploss/config");
      const data = await res.json();
      if (data.data?.config) {
        setConfig(data.data.config);
      }
    } catch (err) {
      console.error("Failed to fetch stoploss config:", err);
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/stoploss/positions");
      const data = await res.json();
      if (data.data?.positions) {
        setPositions(data.data.positions);
      }
    } catch (err) {
      console.error("Failed to fetch positions:", err);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchPositions();
  }, [fetchConfig, fetchPositions]);

  const handleSaveConfig = async () => {
    if (!editValues || Object.keys(editValues).length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/stoploss/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editValues),
      });
      const data = await res.json();
      if (data.data?.config) {
        setConfig(data.data.config);
        setEditing(false);
        setEditValues({});
      } else if (data.error) {
        setError(data.error.message);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleAdjustAll = async () => {
    setAdjusting(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/stoploss/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ all: true }),
      });
      const data = await res.json();
      if (data.data?.summary) {
        await fetchPositions();
      } else if (data.error) {
        setError(data.error.message);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setAdjusting(false);
    }
  };

  const handleSyncPositions = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/stoploss/sync", {
        method: "POST",
      });
      const data = await res.json();
      if (data.data?.sync) {
        await fetchPositions();
      }
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const startEditing = () => {
    if (config) {
      setEditValues({ ...config });
      setEditing(true);
    }
  };

  const cancelEditing = () => {
    setEditing(false);
    setEditValues({});
  };

  const updateEditValue = (key: keyof StoplossConfig, value: string | number) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  };

  if (!config) {
    return <StoplossConfigSkeleton />;
  }

  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="size-4 text-primary" />
            <CardTitle className="text-base">动态止损配置</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {!editing && (
              <Button variant="ghost" size="sm" onClick={startEditing}>
                <Settings className="size-4" />
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={handleSyncPositions} disabled={loading}>
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {error && (
          <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-500">
            <AlertTriangle className="size-3 inline mr-2" />
            {error}
          </div>
        )}

        <div className="grid gap-3">
          <StoplossConfigSection
            config={config}
            editing={editing}
            editValues={editValues}
            updateValue={updateEditValue}
          />

          {editing && (
            <div className="flex gap-2 pt-2">
              <Button size="sm" onClick={handleSaveConfig} disabled={loading}>
                {loading ? "保存中..." : "保存"}
              </Button>
              <Button variant="outline" size="sm" onClick={cancelEditing}>
                取消
              </Button>
            </div>
          )}

          <div className="border-t border-border/60 pt-3 mt-2">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-foreground">持仓止损状态</span>
              <Button size="sm" onClick={handleAdjustAll} disabled={adjusting}>
                {adjusting ? "调整中..." : "调整所有止损"}
              </Button>
            </div>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无持仓监控</p>
            ) : (
              <div className="grid gap-2">
                {positions.map((pos) => (
                  <PositionStoplossItem key={pos.position_id} position={pos} />
                ))}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StoplossConfigSection({
  config,
  editing,
  editValues,
  updateValue,
}: {
  config: StoplossConfig;
  editing: boolean;
  editValues: Partial<StoplossConfig>;
  updateValue: (key: keyof StoplossConfig, value: string | number) => void;
}) {
  const formatPercent = (value: string) => {
    const num = parseFloat(value);
    return num < 0 ? `${num}%` : `${num}%`;
  };

  const displayValue = (key: keyof StoplossConfig) => {
    if (editing && editValues[key] !== undefined) {
      return editValues[key];
    }
    return config[key];
  };

  return (
    <div className="grid grid-cols-2 gap-3 text-sm">
      <div>
        <Label className="text-muted-foreground">基础止损</Label>
        {editing ? (
          <Input
            value={displayValue("base_stoploss")}
            onChange={(e) => updateValue("base_stoploss", e.target.value)}
            className="h-8 mt-1"
          />
        ) : (
          <span className="font-medium text-foreground">{formatPercent(config.base_stoploss)}</span>
        )}
      </div>
      <div>
        <Label className="text-muted-foreground">止损范围</Label>
        <span className="font-medium text-foreground">
          {formatPercent(config.max_stoploss)} ~ {formatPercent(config.min_stoploss)}
        </span>
      </div>
      <div>
        <Label className="text-muted-foreground">高波动阈值</Label>
        {editing ? (
          <Input
            value={displayValue("high_volatility_threshold")}
            onChange={(e) => updateValue("high_volatility_threshold", e.target.value)}
            className="h-8 mt-1"
          />
        ) : (
          <span className="font-medium text-foreground">{config.high_volatility_threshold}</span>
        )}
      </div>
      <div>
        <Label className="text-muted-foreground">低波动阈值</Label>
        {editing ? (
          <Input
            value={displayValue("low_volatility_threshold")}
            onChange={(e) => updateValue("low_volatility_threshold", e.target.value)}
            className="h-8 mt-1"
          />
        ) : (
          <span className="font-medium text-foreground">{config.low_volatility_threshold}</span>
        )}
      </div>
      <div>
        <Label className="text-muted-foreground">调整间隔</Label>
        {editing ? (
          <Input
            type="number"
            value={displayValue("adjustment_interval_minutes")}
            onChange={(e) => updateValue("adjustment_interval_minutes", parseInt(e.target.value) || 30)}
            className="h-8 mt-1"
          />
        ) : (
          <span className="font-medium text-foreground">{config.adjustment_interval_minutes} 分钟</span>
        )}
      </div>
      <div>
        <Label className="text-muted-foreground">最小变动阈值</Label>
        {editing ? (
          <Input
            value={displayValue("throttle_min_change_pct")}
            onChange={(e) => updateValue("throttle_min_change_pct", e.target.value)}
            className="h-8 mt-1"
          />
        ) : (
          <span className="font-medium text-foreground">{parseFloat(config.throttle_min_change_pct) * 100}%</span>
        )}
      </div>
    </div>
  );
}

function PositionStoplossItem({ position }: { position: PositionState }) {
  const [volatility, setVolatility] = useState<VolatilityData | null>(null);

  useEffect(() => {
    fetch(`/api/v1/stoploss/volatility/${position.symbol}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.data?.volatility) {
          setVolatility(data.data.volatility);
        }
      })
      .catch(console.error);
  }, [position.symbol]);

  const volatilityFactor = parseFloat(position.volatility_factor);
  const isHighVolatility = volatilityFactor >= 1.5;
  const isLowVolatility = volatilityFactor <= 0.7;

  const volatilityColor = isHighVolatility
    ? "text-red-500"
    : isLowVolatility
      ? "text-green-500"
      : "text-amber-500";

  const VolatilityIcon = isHighVolatility ? TrendingUp : isLowVolatility ? TrendingDown : TrendingUp;

  return (
    <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-foreground">{position.symbol}</span>
        <div className="flex items-center gap-2">
          <VolatilityIcon className={`size-3 ${volatilityColor}`} />
          <span className={`text-sm ${volatilityColor}`}>{volatilityFactor.toFixed(2)}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">止损</span>
          <span className="font-medium">{parseFloat(position.current_stoploss) * 100}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">入场价</span>
          <span className="font-medium">${parseFloat(position.entry_price).toFixed(2)}</span>
        </div>
        {volatility && (
          <>
            <div className="flex justify-between">
              <span className="text-muted-foreground">ATR%</span>
              <span className="font-medium">{parseFloat(volatility.atr_percent).toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">调整次数</span>
              <span className="font-medium">{position.adjustment_count}</span>
            </div>
          </>
        )}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        最近调整: {formatTime(position.last_adjusted_at)}
      </div>
    </div>
  );
}

function formatTime(value: string): string {
  try {
    const date = new Date(value);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function StoplossConfigSkeleton() {
  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="size-4 text-muted" />
            <div className="h-5 w-24 rounded bg-muted/40 animate-pulse" />
          </div>
          <div className="flex items-center gap-2">
            <div className="size-4 rounded bg-muted/40 animate-pulse" />
            <div className="size-4 rounded bg-muted/40 animate-pulse" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i}>
              <div className="h-4 w-16 rounded bg-muted/40 animate-pulse mb-1" />
              <div className="h-4 w-20 rounded bg-muted/40 animate-pulse" />
            </div>
          ))}
        </div>
        <div className="border-t border-border/60 pt-3 mt-2">
          <div className="h-4 w-32 rounded bg-muted/40 animate-pulse mb-2" />
          <div className="grid gap-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 rounded-lg bg-muted/40 animate-pulse" />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export type StoplossPositionDetail = PositionState & {
  volatility: VolatilityData;
  calculated_stoploss: string;
};