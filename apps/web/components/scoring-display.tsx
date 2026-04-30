/* 入场评分显示组件，展示综合评分和各因子贡献。 */
"use client";

import { Gauge, TrendingUp, TrendingDown, Activity, Volume2, BarChart3, Zap, Settings2, RefreshCw } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Slider } from "./ui/slider";

export type FactorResult = {
  name: string;
  weight: number;
  score: number;
  contribution: number;
};

export type ScoringResult = {
  symbol: string;
  total_score: number;
  weighted_sum: number;
  total_weight: number;
  factors: FactorResult[];
  timestamp: string;
  passed_threshold: boolean;
  threshold: number;
};

export type ScoringDisplayProps = {
  result: ScoringResult;
  onRefresh?: () => void;
  onConfigChange?: (weights: Record<string, number>, threshold: number) => void;
  showConfig?: boolean;
};

const factorIcons: Record<string, typeof Activity> = {
  rsi: Activity,
  macd: TrendingUp,
  volume: Volume2,
  volatility: BarChart3,
  trend: TrendingUp,
  momentum: Zap,
};

const factorLabels: Record<string, string> = {
  rsi: "RSI超卖",
  macd: "MACD金叉",
  volume: "成交量",
  volatility: "波动率",
  trend: "趋势",
  momentum: "动量",
};

const factorColors: Record<string, string> = {
  rsi: "bg-blue-500",
  macd: "bg-purple-500",
  volume: "bg-green-500",
  volatility: "bg-orange-500",
  trend: "bg-indigo-500",
  momentum: "bg-pink-500",
};

export function ScoringDisplay({ result, onRefresh, onConfigChange, showConfig = false }: ScoringDisplayProps) {
  const scorePercentage = Math.round(result.total_score * 100);
  const passedColor = result.passed_threshold ? "text-green-500" : "text-amber-500";
  const passedLabel = result.passed_threshold ? "可入场" : "观望";

  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Gauge className="size-4 text-primary" />
            <CardTitle className="text-base">入场评分 - {result.symbol}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {onRefresh && (
              <Button variant="ghost" size="sm" className="size-8 p-0" onClick={onRefresh}>
                <RefreshCw className="size-4" />
              </Button>
            )}
            <span className={`text-sm font-medium ${passedColor}`}>{passedLabel}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid gap-4">
          {/* 评分仪表盘 */}
          <div className="flex items-center justify-center">
            <ScoreGauge score={scorePercentage} threshold={Math.round(result.threshold * 100)} />
          </div>

          {/* 综合信息 */}
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="flex flex-col items-center gap-1">
              <span className="text-muted-foreground">阈值</span>
              <span className="font-medium">{Math.round(result.threshold * 100)}%</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-muted-foreground">加权总分</span>
              <span className="font-medium">{scorePercentage}%</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-muted-foreground">总权重</span>
              <span className="font-medium">{result.total_weight.toFixed(1)}</span>
            </div>
          </div>

          {/* 因子贡献可视化 */}
          <div className="space-y-3">
            <div className="text-sm font-medium text-muted-foreground">因子贡献分析</div>
            <div className="grid gap-2">
              {result.factors.map((factor) => (
                <FactorContributionBar key={factor.name} factor={factor} />
              ))}
            </div>
          </div>

          {/* 时间戳 */}
          <div className="text-xs text-muted-foreground text-center">
            更新时间: {formatTime(result.timestamp)}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ScoreGauge({ score, threshold }: { score: number; threshold: number }) {
  const radius = 60;
  const stroke = 8;
  const normalizedRadius = radius - stroke / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const scoreColor = score >= threshold ? "#22c55e" : score >= threshold - 10 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative">
      <svg height={radius * 2} width={radius * 2} className="transform -rotate-90">
        {/* 背景圆 */}
        <circle
          stroke="#e5e7eb"
          fill="transparent"
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          strokeWidth={stroke}
        />
        {/* 阈值标记 */}
        <circle
          stroke="#94a3b8"
          fill="transparent"
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          strokeWidth={stroke / 2}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (threshold / 100) * circumference}
          className="opacity-50"
        />
        {/* 评分弧 */}
        <circle
          stroke={scoreColor}
          fill="transparent"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          className="transition-all duration-500"
        />
      </svg>
      {/* 中心数值 */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold" style={{ color: scoreColor }}>{score}</span>
        <span className="text-xs text-muted-foreground">分</span>
      </div>
    </div>
  );
}

function FactorContributionBar({ factor }: { factor: FactorResult }) {
  const IconComponent = factorIcons[factor.name] || Activity;
  const label = factorLabels[factor.name] || factor.name;
  const bgColor = factorColors[factor.name] || "bg-gray-500";
  const contributionPercent = Math.round(factor.contribution * 100);
  const scorePercent = Math.round(factor.score * 100);

  return (
    <div className="flex items-center gap-3 text-sm">
      <div className={`flex items-center gap-2 px-2 py-1 rounded-md ${bgColor}/10`}>
        <IconComponent className="size-3.5" />
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="flex-1 flex items-center gap-2">
        <div className="flex-1 h-2 rounded-full bg-muted/40 overflow-hidden">
          <div
            className={`h-full ${bgColor} transition-all duration-300`}
            style={{ width: `${scorePercent}%` }}
          />
        </div>
        <div className="flex items-center gap-1 min-w-24">
          <span className="text-muted-foreground">{scorePercent}%</span>
          <span className="text-xs text-muted-foreground/60">×{factor.weight.toFixed(1)}</span>
          <span className="font-medium text-primary">={contributionPercent}</span>
        </div>
      </div>
    </div>
  );
}

export function ScoringConfigPanel({
  weights,
  threshold,
  onWeightsChange,
  onThresholdChange,
}: {
  weights: Record<string, number>;
  threshold: number;
  onWeightsChange: (weights: Record<string, number>) => void;
  onThresholdChange: (threshold: number) => void;
}) {
  const [localWeights, setLocalWeights] = useState(weights);
  const [localThreshold, setLocalThreshold] = useState(threshold);

  const handleWeightChange = (factorName: string, value: number[]) => {
    const newWeights = { ...localWeights, [factorName]: value[0] };
    setLocalWeights(newWeights);
    onWeightsChange(newWeights);
  };

  const handleThresholdChange = (value: number[]) => {
    setLocalThreshold(value[0]);
    onThresholdChange(value[0]);
  };

  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <Settings2 className="size-4 text-primary" />
          <CardTitle className="text-base">评分参数配置</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid gap-4">
          {/* 阈值配置 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">入场阈值</span>
              <span className="font-medium">{Math.round(localThreshold * 100)}%</span>
            </div>
            <Slider
              value={[localThreshold]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={handleThresholdChange}
            />
          </div>

          {/* 因子权重配置 */}
          <div className="space-y-3">
            <div className="text-sm font-medium text-muted-foreground">因子权重</div>
            {Object.entries(localWeights).map(([name, weight]) => (
              <div key={name} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`size-2 rounded-full ${factorColors[name] || "bg-gray-500"}`} />
                    <span>{factorLabels[name] || name}</span>
                  </div>
                  <span className="font-medium">{weight.toFixed(1)}</span>
                </div>
                <Slider
                  value={[weight]}
                  min={0}
                  max={3}
                  step={0.1}
                  onValueChange={(value) => handleWeightChange(name, value)}
                />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function ScoringDisplaySkeleton() {
  return (
    <Card className="bg-card/90">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Gauge className="size-4 text-muted" />
            <div className="h-5 w-32 rounded bg-muted/40 animate-pulse" />
          </div>
          <div className="h-4 w-12 rounded bg-muted/40 animate-pulse" />
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid gap-4">
          {/* 仪表盘骨架 */}
          <div className="flex items-center justify-center">
            <div className="size-[120px] rounded-full bg-muted/40 animate-pulse" />
          </div>

          {/* 信息骨架 */}
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex flex-col items-center gap-1">
                <div className="h-3 w-12 rounded bg-muted/40 animate-pulse" />
                <div className="h-4 w-8 rounded bg-muted/40 animate-pulse" />
              </div>
            ))}
          </div>

          {/* 因子骨架 */}
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-6 w-20 rounded bg-muted/40 animate-pulse" />
                <div className="flex-1 h-2 rounded bg-muted/40 animate-pulse" />
                <div className="h-4 w-20 rounded bg-muted/40 animate-pulse" />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
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
      second: "2-digit",
    });
  } catch {
    return value;
  }
}

/* 评分API调用Hook */
export function useScoringApi() {
  const [currentScore, setCurrentScore] = useState<ScoringResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateScore = useCallback(async (symbol: string, data: Record<string, unknown>) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/scoring/calculate?symbol=${symbol}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        // Note: 实际应该用POST传递data，这里简化处理
      });
      if (!response.ok) throw new Error("计算失败");
      const json = await response.json();
      if (json.data?.item) {
        setCurrentScore(json.data.item);
        return json.data.item;
      }
      throw new Error("无评分结果");
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getCurrentScore = useCallback(async (symbol: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/scoring/current?symbol=${symbol}`);
      if (!response.ok) throw new Error("获取失败");
      const json = await response.json();
      if (json.data?.item) {
        setCurrentScore(json.data.item);
        return json.data.item;
      }
      return null;
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getFactors = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/scoring/factors");
      if (!response.ok) throw new Error("获取失败");
      const json = await response.json();
      return json.data || null;
    } catch {
      return null;
    }
  }, []);

  const updateWeights = useCallback(async (weights: Record<string, number>, token?: string) => {
    try {
      const response = await fetch("/api/v1/scoring/factors", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ weights }),
      });
      if (!response.ok) throw new Error("更新失败");
      const json = await response.json();
      return json.data?.updated ?? false;
    } catch {
      return false;
    }
  }, []);

  const updateThreshold = useCallback(async (threshold: number, token?: string) => {
    try {
      const response = await fetch("/api/v1/scoring/threshold", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ threshold }),
      });
      if (!response.ok) throw new Error("更新失败");
      const json = await response.json();
      return json.data?.updated ?? false;
    } catch {
      return false;
    }
  }, []);

  return {
    currentScore,
    isLoading,
    error,
    calculateScore,
    getCurrentScore,
    getFactors,
    updateWeights,
    updateThreshold,
  };
}

/* 默认评分结果（用于fallback） */
export function getDefaultScoringResult(symbol: string = "BTC/USDT"): ScoringResult {
  return {
    symbol,
    total_score: 0.72,
    weighted_sum: 4.32,
    total_weight: 6.0,
    factors: [
      { name: "rsi", weight: 1.0, score: 0.85, contribution: 0.85 },
      { name: "macd", weight: 1.0, score: 0.78, contribution: 0.78 },
      { name: "volume", weight: 0.8, score: 0.65, contribution: 0.52 },
      { name: "volatility", weight: 0.6, score: 0.70, contribution: 0.42 },
      { name: "trend", weight: 1.2, score: 0.82, contribution: 0.98 },
      { name: "momentum", weight: 0.8, score: 0.75, contribution: 0.60 },
    ],
    timestamp: new Date().toISOString(),
    passed_threshold: true,
    threshold: 0.60,
  };
}