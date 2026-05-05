/* 这个文件负责渲染配置管理界面。 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import {
  TerminalShell,
  ControlPanel,
  FieldRow,
  TerminalInput,
  TerminalSelect,
} from "../../components/terminal";
import { FeedbackBanner } from "../../components/feedback-banner";
import { LoadingBanner } from "../../components/loading-banner";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { readFeedback } from "../../lib/feedback";

type ConfigItem = {
  key: string;
  value: string;
  description?: string;
};

type ConfigSection = {
  section: string;
  description: string;
  config: Record<string, string>;
  source?: string;
};

type ConfigSchema = {
  sections: Record<string, { description: string; keys: string[] }>;
  sources: Record<string, unknown>;
  sensitive_keys: string[];
};

const SECTION_LABELS: Record<string, string> = {
  network: "网络配置",
  trading: "交易配置",
  risk: "风控配置",
  alert: "告警配置",
  research: "研究配置",
  auth: "认证配置",
  binance: "币安配置",
};

const KEY_DESCRIPTIONS: Record<string, string> = {
  HTTP_PROXY: "HTTP 代理地址",
  HTTPS_PROXY: "HTTPS 代理地址",
  ALL_PROXY: "全局代理地址",
  NO_PROXY: "不走代理的地址列表",
  QUANT_BINANCE_MARKET_BASE_URL: "币安市场 API 地址",
  QUANT_BINANCE_ACCOUNT_BASE_URL: "币安账户 API 地址",
  QUANT_BINANCE_TIMEOUT_SECONDS: "币安 API 请求超时时间",
  QUANT_RUNTIME_MODE: "运行模式 (dry-run/live/paper)",
  QUANT_MARKET_SYMBOLS: "监控的交易对列表",
  QUANT_ALLOW_LIVE_EXECUTION: "是否允许实盘执行",
  QUANT_LIVE_ALLOWED_SYMBOLS: "实盘允许的交易对列表",
  QUANT_LIVE_MAX_STAKE_USDT: "单笔最大投入金额",
  QUANT_LIVE_MAX_OPEN_TRADES: "最大同时持仓数",
  QUANT_FREQTRADE_API_URL: "Freqtrade API 地址",
  QUANT_FREQTRADE_API_USERNAME: "Freqtrade API 用户名",
  QUANT_FREQTRADE_API_PASSWORD: "Freqtrade API 密码",
  QUANT_FREQTRADE_API_TIMEOUT_SECONDS: "Freqtrade API 超时时间",
  QUANT_RISK_DAILY_MAX_LOSS_PCT: "每日最大亏损百分比",
  QUANT_RISK_MAX_TRADES_PER_DAY: "每日最大交易次数",
  QUANT_RISK_CRASH_THRESHOLD_PCT: "熔断阈值百分比",
  QUANT_QLIB_DRY_RUN_MIN_SHARPE: "最小夏普比率要求",
  QUANT_QLIB_DRY_RUN_MIN_WIN_RATE: "最小胜率要求",
  QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT: "最大回撤百分比",
  QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK: "最大连续亏损次数",
  QUANT_QLIB_DRY_RUN_MIN_SCORE: "最小综合评分",
  QUANT_QLIB_FORCE_TOP_CANDIDATE: "是否强制选择最优候选",
  QUANT_QLIB_SESSION_ID: "Qlib 研究会话 ID",
  QUANT_ADMIN_USERNAME: "管理员用户名",
  QUANT_ADMIN_PASSWORD: "管理员密码",
  QUANT_SESSION_TTL_SECONDS: "会话有效期（秒）",
  BINANCE_API_KEY: "币安 API Key",
  BINANCE_API_SECRET: "币安 API Secret",
};

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default function ConfigPage({}: PageProps) {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [schema, setSchema] = useState<ConfigSchema | null>(null);
  const [sections, setSections] = useState<Record<string, ConfigSection>>({});
  const [selectedSection, setSelectedSection] = useState<string>("network");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    // Fetch schema and all config via /api/control proxy
    Promise.all([
      fetch("/api/control/config/schema", { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => data.error ? null : data.data),
      fetch("/api/control/config", { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => data.error ? null : data.data),
    ])
      .then(([schemaData, configData]) => {
        clearTimeout(timeoutId);
        if (schemaData) {
          setSchema(schemaData);
        }
        if (configData?.sections) {
          setSections(configData.sections);
        }
        setIsLoading(false);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  // Filter config items based on search query
  const filteredConfig = useMemo(() => {
    const currentSection = sections[selectedSection];
    if (!currentSection?.config) {
      return [];
    }

    const items: ConfigItem[] = [];
    for (const [key, value] of Object.entries(currentSection.config)) {
      const description = KEY_DESCRIPTIONS[key] || "";
      if (
        searchQuery === "" ||
        key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        value.toLowerCase().includes(searchQuery.toLowerCase()) ||
        description.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        items.push({ key, value, description });
      }
    }
    return items;
  }, [sections, selectedSection, searchQuery]);

  // Get available sections
  const availableSections = useMemo(() => {
    if (!schema?.sections) {
      return Object.keys(SECTION_LABELS);
    }
    return Object.keys(schema.sections);
  }, [schema]);

  // Build section options for select
  const sectionOptions = useMemo(() => {
    return availableSections.map((section) => ({
      value: section,
      label: SECTION_LABELS[section] || section,
    }));
  }, [availableSections]);

  // Calculate stats
  const totalConfigItems = useMemo(() => {
    return Object.values(sections).reduce(
      (sum, s) => sum + Object.keys(s.config || {}).length,
      0
    );
  }, [sections]);

  return (
    <TerminalShell
      breadcrumb="系统 / 配置"
      title="配置"
      subtitle="查看和管理系统配置项，包括网络、交易、风控等分节配置"
      currentPath="/config"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      {isLoading && <LoadingBanner />}

      {!session.isAuthenticated ? (
        <ControlPanel title="需要登录">
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">登录后才能查看完整配置信息</p>
            <Button asChild variant="outline">
              <Link href="/login?next=%2Fconfig">前往登录</Link>
            </Button>
          </div>
        </ControlPanel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          {/* 左侧：配置分节选择 */}
          <div className="space-y-4">
            <ControlPanel title="配置分节">
              <FieldRow label="选择类别">
                <TerminalSelect
                  value={selectedSection}
                  onChange={setSelectedSection}
                  options={sectionOptions}
                />
              </FieldRow>
            </ControlPanel>

            {/* 配置状态 */}
            <ControlPanel title="配置状态">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">总配置分节</span>
                  <span className="text-sm font-mono">{availableSections.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">已配置项</span>
                  <span className="text-sm font-mono">{totalConfigItems}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">敏感配置</span>
                  <span className="text-sm font-mono">{schema?.sensitive_keys?.length || 0}</span>
                </div>
              </div>
            </ControlPanel>
          </div>

          {/* 右侧：配置项列表 */}
          <div className="space-y-4">
            {/* 搜索栏 */}
            <ControlPanel title={SECTION_LABELS[selectedSection] || selectedSection}>
              <FieldRow label="搜索配置项">
                <TerminalInput
                  value={searchQuery}
                  onChange={setSearchQuery}
                  placeholder="输入关键词搜索..."
                />
              </FieldRow>

              <div className="flex items-center gap-2 pt-2">
                <Badge variant="outline">
                  {filteredConfig.length} 项配置
                </Badge>
                {sections[selectedSection]?.source && (
                  <Badge variant="outline">
                    来源: {sections[selectedSection].source}
                  </Badge>
                )}
              </div>
            </ControlPanel>

            {/* 配置项列表 */}
            <div className="terminal-card">
              <div className="terminal-card-header">
                <span className="text-xs text-muted-foreground">
                  {sections[selectedSection]?.description || "当前分节的配置项"}
                </span>
              </div>
              <div className="space-y-2">
                {filteredConfig.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    <p className="text-sm">
                      {searchQuery
                        ? "没有找到匹配的配置项"
                        : "当前分节没有配置项"}
                    </p>
                  </div>
                ) : (
                  filteredConfig.map((item) => {
                    const isSensitive = schema?.sensitive_keys?.includes(item.key);
                    const isRedacted = item.value === "***REDACTED***";

                    return (
                      <div
                        key={item.key}
                        className="flex items-start justify-between gap-3 rounded border border-border/40 bg-background/40 p-3"
                      >
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-foreground">
                              {item.key}
                            </span>
                            {isSensitive && (
                              <Badge variant="warning" className="text-xs">
                                敏感
                              </Badge>
                            )}
                          </div>
                          {item.description && (
                            <p className="text-xs text-muted-foreground">
                              {item.description}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center">
                          {isRedacted ? (
                            <Badge variant="outline" className="text-xs">
                              已脱敏
                            </Badge>
                          ) : (
                            <code className="rounded bg-muted/60 px-2 py-1 text-xs font-mono text-foreground">
                              {item.value || "(空)"}
                            </code>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </TerminalShell>
  );
}
