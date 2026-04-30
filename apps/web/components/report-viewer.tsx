"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface ReportViewerProps {
  reportType?: "daily" | "weekly";
  date?: string;
}

interface ReportData {
  report_type: string;
  generated_at: string;
  period: {
    start: string;
    end: string;
  };
  summary: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    total_profit: number;
    win_rate: number;
  };
  positions: Array<{
    symbol: string;
    entry_price: number;
    current_price: number;
    profit: number;
    status: string;
  }>;
  risk_analysis?: {
    max_drawdown: number;
    volatility: number;
    sharpe_ratio: number;
  };
  factor_analysis?: Array<{
    factor: string;
    contribution: number;
    weight: number;
  }>;
}

export function ReportViewer({ reportType = "daily", date }: ReportViewerProps) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReport();
  }, [reportType, date]);

  const fetchReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = reportType === "weekly"
        ? `/api/v1/report/weekly?week_start=${date || ""}`
        : `/api/v1/report/daily?date=${date || ""}`;
      const res = await fetch(endpoint);
      if (!res.ok) throw new Error("Failed to fetch report");
      const data = await res.json();
      setReport(data.data || data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-muted rounded w-1/4" />
            <div className="h-4 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-red-500">Error: {error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!report) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-muted-foreground">No report available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{reportType === "weekly" ? "Weekly Report" : "Daily Report"}</span>
            <span className="text-sm text-muted-foreground">
              {new Date(report.generated_at).toLocaleString()}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Total Trades</p>
              <p className="text-2xl font-bold">{report.summary.total_trades}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Win Rate</p>
              <p className="text-2xl font-bold text-green-500">
                {(report.summary.win_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Profit</p>
              <p className={`text-2xl font-bold ${report.summary.total_profit >= 0 ? "text-green-500" : "text-red-500"}`}>
                {report.summary.total_profit >= 0 ? "+" : ""}{report.summary.total_profit.toFixed(2)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Win/Loss</p>
              <p className="text-2xl font-bold">
                {report.summary.winning_trades}/{report.summary.losing_trades}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Risk Analysis (Weekly) */}
      {report.risk_analysis && (
        <Card>
          <CardHeader>
            <CardTitle>Risk Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Max Drawdown</p>
                <p className="text-lg font-semibold text-red-500">
                  {report.risk_analysis.max_drawdown.toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Volatility</p>
                <p className="text-lg font-semibold">
                  {report.risk_analysis.volatility.toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Sharpe Ratio</p>
                <p className="text-lg font-semibold text-green-500">
                  {report.risk_analysis.sharpe_ratio.toFixed(2)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Factor Analysis (Weekly) */}
      {report.factor_analysis && report.factor_analysis.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Factor Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {report.factor_analysis.map((factor) => (
                <div key={factor.factor} className="flex items-center justify-between">
                  <span className="text-sm">{factor.factor}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      Weight: {factor.weight.toFixed(2)}
                    </span>
                    <span className={`text-sm font-semibold ${factor.contribution >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {factor.contribution >= 0 ? "+" : ""}{factor.contribution.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Positions */}
      {report.positions && report.positions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Positions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {report.positions.map((pos, i) => (
                <div key={i} className="flex items-center justify-between border-b pb-2">
                  <div>
                    <p className="font-medium">{pos.symbol}</p>
                    <p className="text-xs text-muted-foreground">
                      Entry: {pos.entry_price} | Current: {pos.current_price}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`font-semibold ${pos.profit >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {pos.profit >= 0 ? "+" : ""}{pos.profit.toFixed(2)}%
                    </p>
                    <p className="text-xs text-muted-foreground">{pos.status}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}