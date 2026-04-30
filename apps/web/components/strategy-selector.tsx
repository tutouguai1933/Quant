/* 策略选择器组件 - 支持多策略模板框架 */
"use client";

import { Settings, TrendingUp, Grid3X3, Check, RefreshCw } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

export type StrategyInfo = {
  name: string;
  display_name: string;
  description: string;
  config: Record<string, unknown>;
  config_schema: {
    parameters: Record<string, {
      type: string;
      default?: unknown;
      min?: number;
      max?: number;
      options?: string[];
      description: string;
    }>;
  };
  is_current: boolean;
};

export type StrategySelectorProps = {
  onStrategyChange?: (strategyName: string) => void;
  onConfigChange?: (strategyName: string, config: Record<string, unknown>) => void;
};

const strategyIcons: Record<string, React.ReactNode> = {
  trend: <TrendingUp className="size-4" />,
  grid: <Grid3X3 className="size-4" />,
};

export function StrategySelector({ onStrategyChange, onConfigChange }: StrategySelectorProps) {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [currentStrategy, setCurrentStrategy] = useState<string>("");
  const [selectedStrategy, setSelectedStrategy] = useState<string>("");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [schema, setSchema] = useState<StrategyInfo["config_schema"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch strategy list
  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/strategy/list");
      const data = await res.json();
      if (data.error) {
        setError(data.error.message);
      } else {
        setStrategies(data.data.strategies || []);
        const current = data.data.strategies?.find((s: StrategyInfo) => s.is_current);
        if (current) {
          setCurrentStrategy(current.name);
          setSelectedStrategy(current.name);
          setConfig(current.config || {});
          setSchema(current.config_schema || null);
        }
      }
    } catch (err) {
      setError("无法加载策略列表");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch current strategy config
  const fetchConfig = useCallback(async (strategyName: string) => {
    try {
      const res = await fetch(`/api/v1/strategy/config?strategy_name=${strategyName}`);
      const data = await res.json();
      if (data.data) {
        setConfig(data.data.config || {});
        setSchema(data.data.schema || null);
      }
    } catch (err) {
      console.error("Failed to fetch config:", err);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // Handle strategy selection
  const handleStrategySelect = (strategyName: string) => {
    setSelectedStrategy(strategyName);
    fetchConfig(strategyName);
  };

  // Handle config value change
  const handleConfigChange = (paramName: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [paramName]: value }));
  };

  // Save config
  const handleSaveConfig = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/strategy/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_name: selectedStrategy,
          config,
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error.message);
      } else {
        onConfigChange?.(selectedStrategy, config);
      }
    } catch (err) {
      setError("保存配置失败");
    } finally {
      setSaving(false);
    }
  };

  // Switch strategy
  const handleSwitchStrategy = async () => {
    if (selectedStrategy === currentStrategy) return;

    setSwitching(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/strategy/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: selectedStrategy }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error.message);
      } else {
        setCurrentStrategy(selectedStrategy);
        onStrategyChange?.(selectedStrategy);
        // Refresh strategies to update is_current flags
        fetchStrategies();
      }
    } catch (err) {
      setError("切换策略失败");
    } finally {
      setSwitching(false);
    }
  };

  // Render parameter input based on type
  const renderParamInput = (paramName: string, paramConfig: StrategyInfo["config_schema"]["parameters"][string]) => {
    const value = config[paramName] ?? paramConfig.default;

    if (paramConfig.type === "number") {
      return (
        <Input
          type="number"
          value={value as number}
          min={paramConfig.min}
          max={paramConfig.max}
          onChange={(e) => handleConfigChange(paramName, parseFloat(e.target.value) || 0)}
          className="h-9"
        />
      );
    }

    if (paramConfig.type === "string" && paramConfig.options) {
      return (
        <select
          value={value as string}
          onChange={(e) => handleConfigChange(paramName, e.target.value)}
          className="h-9 w-full rounded-xl border border-border/70 bg-background/70 px-3 text-sm text-foreground shadow-sm"
        >
          {paramConfig.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    if (paramConfig.type === "string") {
      return (
        <Input
          type="text"
          value={value as string}
          onChange={(e) => handleConfigChange(paramName, e.target.value)}
          className="h-9"
        />
      );
    }

    if (paramConfig.type === "boolean") {
      return (
        <input
          type="checkbox"
          checked={value as boolean}
          onChange={(e) => handleConfigChange(paramName, e.target.checked)}
          className="h-4 w-4 rounded border-border/70"
        />
      );
    }

    return (
      <Input
        type="text"
        value={String(value)}
        onChange={(e) => handleConfigChange(paramName, e.target.value)}
        className="h-9"
      />
    );
  };

  if (loading) {
    return (
      <Card className="bg-card/90">
        <CardHeader>
          <div className="flex items-center gap-3">
            <Settings className="size-4 text-muted animate-pulse" />
            <CardTitle className="text-base">策略选择</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="h-32 flex items-center justify-center text-muted-foreground">
            加载中...
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card/90">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Settings className="size-4 text-primary" />
            <CardTitle className="text-base">策略选择</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStrategies}
            disabled={loading}
          >
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-2 space-y-4">
        {error && (
          <div className="rounded-lg border border-red-400/30 bg-red-500/12 px-3 py-2 text-sm text-red-100">
            {error}
          </div>
        )}

        {/* Strategy list */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground">选择策略</label>
          <div className="grid grid-cols-2 gap-2">
            {strategies.map((strategy) => (
              <button
                key={strategy.name}
                onClick={() => handleStrategySelect(strategy.name)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-colors ${
                  selectedStrategy === strategy.name
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border/60 bg-muted/20 text-muted-foreground hover:bg-muted/30"
                }`}
              >
                {strategyIcons[strategy.name] || <Settings className="size-4" />}
                <span className="flex-1">{strategy.display_name}</span>
                {strategy.is_current && (
                  <Badge variant="success" className="text-xs">当前</Badge>
                )}
                {selectedStrategy === strategy.name && !strategy.is_current && (
                  <Check className="size-3.5 text-primary" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Strategy description */}
        {selectedStrategy && (
          <div className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
            <p className="text-sm text-muted-foreground">
              {strategies.find((s) => s.name === selectedStrategy)?.description}
            </p>
          </div>
        )}

        {/* Configuration form */}
        {schema?.parameters && (
          <div className="space-y-3">
            <label className="text-sm font-medium text-muted-foreground">参数配置</label>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(schema.parameters).map(([paramName, paramConfig]) => (
                <div key={paramName} className="space-y-1">
                  <label className="text-xs text-muted-foreground">{paramConfig.description}</label>
                  {renderParamInput(paramName, paramConfig)}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveConfig}
            disabled={saving || !selectedStrategy}
          >
            {saving ? "保存中..." : "保存配置"}
          </Button>
          {selectedStrategy !== currentStrategy && (
            <Button
              variant="default"
              size="sm"
              onClick={handleSwitchStrategy}
              disabled={switching}
            >
              {switching ? "切换中..." : "切换策略"}
            </Button>
          )}
        </div>

        {/* Current strategy info */}
        <div className="rounded-lg border border-border/60 bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
          当前激活策略: <span className="font-medium text-foreground">
            {strategies.find((s) => s.name === currentStrategy)?.display_name || currentStrategy}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export function StrategySelectorSkeleton() {
  return (
    <Card className="bg-card/90">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="size-4 rounded bg-muted/40 animate-pulse" />
          <div className="h-5 w-16 rounded bg-muted/40 animate-pulse" />
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid grid-cols-2 gap-2 mb-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-10 rounded-xl bg-muted/40 animate-pulse" />
          ))}
        </div>
        <div className="h-8 rounded-lg bg-muted/40 animate-pulse mb-4" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-12 rounded bg-muted/40 animate-pulse" />
              <div className="h-9 rounded bg-muted/40 animate-pulse" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}