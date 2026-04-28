/* 这个文件负责渲染配置管理界面。 */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { FeedbackBanner } from "../../components/feedback-banner";
import { PageHero } from "../../components/page-hero";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Skeleton } from "../../components/ui/skeleton";
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

const SECTION_ICONS: Record<string, string> = {
  network: "🌐",
  trading: "📊",
  risk: "⚠️",
  alert: "🔔",
  research: "🔬",
  auth: "🔐",
  binance: "₿",
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

    // Fetch schema and all config
    Promise.all([
      fetch("/api/v1/config/schema", { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => data.error ? null : data.data),
      fetch("/api/v1/config", { signal: controller.signal })
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

  return (
    <AppShell
      title="配置中心"
      subtitle="查看和管理系统配置项，包括网络、交易、风控等分节配置"
      currentPath="/config"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="系统配置"
        title="配置管理"
        description="查看当前系统配置项，了解各配置分节的含义和当前值"
      />

      {!session.isAuthenticated ? (
        <Card>
          <CardHeader>
            <CardTitle>需要登录</CardTitle>
            <CardDescription>登录后才能查看完整配置信息</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href="/login?next=%2Fconfig">前往登录</Link>
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Search bar */}
          <div className="flex items-center gap-3">
            <Input
              type="text"
              placeholder="搜索配置项..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="max-w-md"
            />
            <Badge variant="outline">
              {filteredConfig.length} 项配置
            </Badge>
          </div>

          <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
            {/* Left: Section navigation */}
            <Card className="h-fit">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">配置分节</CardTitle>
                <CardDescription>选择要查看的配置类别</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1">
                {availableSections.map((section) => {
                  const isActive = selectedSection === section;
                  const label = SECTION_LABELS[section] || section;
                  const icon = SECTION_ICONS[section] || "";
                  const sectionData = sections[section];
                  const configCount = Object.keys(sectionData?.config || {}).length;

                  return (
                    <button
                      key={section}
                      onClick={() => setSelectedSection(section)}
                      className={[
                        "w-full rounded-lg border px-3 py-2.5 text-left transition-colors",
                        isActive
                          ? "border-primary/40 bg-primary/10 text-foreground"
                          : "border-border/60 bg-background/70 text-muted-foreground hover:border-border hover:bg-accent hover:text-accent-foreground",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">{icon}</span>
                          <span className="text-sm font-medium">{label}</span>
                        </div>
                        <Badge variant={configCount > 0 ? "success" : "outline"} className="text-xs">
                          {configCount}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-1">
                        {sections[section]?.description || SECTION_LABELS[section] || ""}
                      </p>
                    </button>
                  );
                })}
              </CardContent>
            </Card>

            {/* Right: Config items display */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle>
                      {SECTION_LABELS[selectedSection] || selectedSection}
                    </CardTitle>
                    <CardDescription>
                      {sections[selectedSection]?.description || "当前分节的配置项"}
                    </CardDescription>
                  </div>
                  {sections[selectedSection]?.source && (
                    <Badge variant="outline" className="text-xs">
                      来源: {sections[selectedSection].source}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {filteredConfig.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    <p className="text-sm">
                      {searchQuery
                        ? "没有找到匹配的配置项"
                        : "当前分节没有配置项"}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredConfig.map((item) => {
                      const isSensitive = schema?.sensitive_keys?.includes(item.key);
                      const isRedacted = item.value === "***REDACTED***";

                      return (
                        <div
                          key={item.key}
                          className="rounded-xl border border-border/60 bg-background/70 p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
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
                            <div className="flex items-center gap-2">
                              {isRedacted ? (
                                <Badge variant="outline" className="text-xs">
                                  已脱敏
                                </Badge>
                              ) : (
                                <code className="rounded-lg bg-muted/60 px-2 py-1 text-xs font-mono text-foreground">
                                  {item.value || "(空)"}
                                </code>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Config validation summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">配置状态</CardTitle>
              <CardDescription>配置完整性和验证状态</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border border-border/60 bg-background/70 p-3">
                  <p className="text-xs text-muted-foreground">总配置分节</p>
                  <p className="mt-1 text-lg font-semibold">
                    {availableSections.length}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-background/70 p-3">
                  <p className="text-xs text-muted-foreground">已配置项</p>
                  <p className="mt-1 text-lg font-semibold">
                    {Object.values(sections).reduce(
                      (sum, s) => sum + Object.keys(s.config || {}).length,
                      0
                    )}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-background/70 p-3">
                  <p className="text-xs text-muted-foreground">敏感配置</p>
                  <p className="mt-1 text-lg font-semibold">
                    {schema?.sensitive_keys?.length || 0}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </AppShell>
  );
}