/* 因子分析面板组件，展示因子贡献分析、相关性矩阵和有效性评估。 */
"use client";

import { Activity, BarChart3, CorrelationIcon as Correlation, TrendingUp, AlertTriangle, CheckCircle, Settings } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

type FactorContribution = {
  factor_name: string;
  weight: number;
  avg_score: number;
  avg_contribution: number;
  contribution_rate: number;
  impact_count: number;
  positive_impact_rate: number;
  correlation_with_pnl: number;
};

type FactorAnalysisResult = {
  strategy_id: string;
  timestamp: string;
  contributions: FactorContribution[];
  total_contribution: number;
  top_factors: string[];
  weak_factors: string[];
  recommendations: string[];
};

type FactorEffectiveness = {
  factor_name: string;
  period: string;
  effectiveness_score: number;
  stability_score: number;
  predictive_power: number;
  decay_rate: number;
  recommendation: string;
};

type CorrelationMatrix = {
  factors: string[];
  matrix: number[][];
  timestamp: string;
};

export function FactorAnalysisPanel() {
  const [analysis, setAnalysis] = useState<FactorAnalysisResult | null>(null);
  const [correlation, setCorrelation] = useState<CorrelationMatrix | null>(null);
  const [effectiveness, setEffectiveness] = useState<FactorEffectiveness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [strategyId, setStrategyId] = useState("default");
  const [period, setPeriod] = useState("30d");

  useEffect(() => {
    fetchAnalysis();
  }, [strategyId]);

  useEffect(() => {
    fetchEffectiveness();
  }, [period]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/factor/analysis?strategy_id=${strategyId}`);
      const data = await res.json();
      if (data.error) {
        setError(data.error.message);
      } else {
        setAnalysis(data.data.analysis);
      }
    } catch (e) {
      setError("获取因子分析失败");
    } finally {
      setLoading(false);
    }
  };

  const fetchCorrelation = async () => {
    try {
      const res = await fetch("/api/v1/factor/correlation");
      const data = await res.json();
      if (!data.error) {
        setCorrelation(data.data.correlation);
      }
    } catch (e) {
      // 忽略相关性获取失败
    }
  };

  const fetchEffectiveness = async () => {
    try {
      const res = await fetch(`/api/v1/factor/effectiveness?period=${period}`);
      const data = await res.json();
      if (!data.error) {
        setEffectiveness(data.data.effectiveness);
      }
    } catch (e) {
      // 忽略有效性获取失败
    }
  };

  useEffect(() => {
    fetchCorrelation();
  }, []);

  const getRecommendationBadge = (rec: string) => {
    switch (rec) {
      case "keep":
        return <Badge variant="success">保持</Badge>;
      case "adjust":
        return <Badge variant="warning">调整</Badge>;
      case "remove":
        return <Badge variant="danger">移除</Badge>;
      default:
        return <Badge variant="neutral">{rec}</Badge>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return "text-green-500";
    if (score >= 0.4) return "text-yellow-500";
    return "text-red-500";
  };

  return (
    <div className="space-y-4">
      {/* 控制栏 */}
      <Card className="bg-card/90">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BarChart3 className="size-4 text-primary" />
              <CardTitle className="text-base">因子分析</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <Select value={strategyId} onValueChange={setStrategyId}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="选择策略" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">默认策略</SelectItem>
                  <SelectItem value="btc">BTC策略</SelectItem>
                  <SelectItem value="eth">ETH策略</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={fetchAnalysis}>
                刷新
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {loading && <div className="text-center py-8 text-muted-foreground">加载中...</div>}
      {error && <div className="text-center py-8 text-red-500">{error}</div>}

      {/* 因子贡献分析 */}
      {analysis && (
        <Card className="bg-card/90">
          <CardHeader>
            <div className="flex items-center gap-3">
              <TrendingUp className="size-4 text-primary" />
              <CardTitle className="text-base">因子贡献分析</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="space-y-3">
              {/* 主要因子 */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">主要因子:</span>
                {analysis.top_factors.length > 0 ? (
                  analysis.top_factors.map((f) => (
                    <Badge key={f} variant="success">{f}</Badge>
                  ))
                ) : (
                  <span className="text-sm">暂无数据</span>
                )}
              </div>

              {/* 弱因子 */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">弱因子:</span>
                {analysis.weak_factors.length > 0 ? (
                  analysis.weak_factors.map((f) => (
                    <Badge key={f} variant="warning">{f}</Badge>
                  ))
                ) : (
                  <span className="text-sm">暂无</span>
                )}
              </div>

              {/* 因子贡献列表 */}
              <div className="border rounded-md divide-y">
                {analysis.contributions.map((c) => (
                  <div key={c.factor_name} className="p-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="font-medium">{c.factor_name}</span>
                      <Badge variant="neutral">权重: {c.weight.toFixed(2)}</Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className={getScoreColor(c.avg_score)}>
                        评分: {c.avg_score.toFixed(3)}
                      </span>
                      <span className={getScoreColor(c.avg_contribution)}>
                        贡献: {c.avg_contribution.toFixed(3)}
                      </span>
                      <span className="text-muted-foreground">
                        正向率: {(c.positive_impact_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* 建议 */}
              {analysis.recommendations.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Settings className="size-3 text-muted-foreground" />
                    <span className="text-sm font-medium">优化建议</span>
                  </div>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {analysis.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <CheckCircle className="size-3 mt-0.5 text-primary" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 因子相关性矩阵 */}
      {correlation && correlation.factors.length > 0 && (
        <Card className="bg-card/90">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Activity className="size-4 text-primary" />
              <CardTitle className="text-base">因子相关性</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="p-2"></th>
                    {correlation.factors.map((f) => (
                      <th key={f} className="p-2 text-center font-medium">{f}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {correlation.matrix.map((row, i) => (
                    <tr key={i}>
                      <td className="p-2 font-medium">{correlation.factors[i]}</td>
                      {row.map((val, j) => (
                        <td
                          key={j}
                          className={`p-2 text-center ${val >= 0.5 ? "bg-green-100 dark:bg-green-900/20" : val <= -0.3 ? "bg-red-100 dark:bg-red-900/20" : ""}`}
                        >
                          {val.toFixed(2)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 因子有效性评估 */}
      <Card className="bg-card/90">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="size-4 text-primary" />
              <CardTitle className="text-base">因子有效性</CardTitle>
            </div>
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="w-[100px]">
                <SelectValue placeholder="周期" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7天</SelectItem>
                <SelectItem value="30d">30天</SelectItem>
                <SelectItem value="90d">90天</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          {effectiveness.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground">暂无数据</div>
          ) : (
            <div className="space-y-2">
              {effectiveness.map((e) => (
                <div key={e.factor_name} className="border rounded-md p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{e.factor_name}</span>
                    {getRecommendationBadge(e.recommendation)}
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">有效性:</span>
                      <span className={`ml-1 ${getScoreColor(e.effectiveness_score)}`}>
                        {e.effectiveness_score.toFixed(2)}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">稳定性:</span>
                      <span className={`ml-1 ${getScoreColor(e.stability_score)}`}>
                        {e.stability_score.toFixed(2)}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">预测力:</span>
                      <span className={`ml-1 ${getScoreColor(e.predictive_power)}`}>
                        {e.predictive_power.toFixed(2)}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">衰减率:</span>
                      <span className={`ml-1 ${e.decay_rate > 0.2 ? "text-red-500" : "text-green-500"}`}>
                        {(e.decay_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}