# 前端优化开发计划

> 创建时间：2026-05-11
> 计划执行时间：2026-05-11 05:00 AM (北京时间)

---

## 一、任务概览

| ID | 任务 | 估计时间 | 优先级 |
|----|------|----------|--------|
| 1 | 入场状态卡片增强 | 45分钟 | P0 |
| 2 | 运维页巡检统计增强 | 30分钟 | P1 |
| 3 | 文档更新 | 15分钟 | P2 |
| 4 | 性能优化 - 合并刷新 | 45分钟 | P1 |
| 5 | 部署和验证 | 20分钟 | P0 |
| 6 | 周期历史详情面板优化 | 30分钟 | P2 |
| 7 | RSI概览筛选功能 | 20分钟 | P2 |
| 8 | 候选队列增强 | 30分钟 | P1 |
| 9 | 余额页USD估值 | 45分钟 | P0 |

**总计开发时间：约4小时**

---

## 二、详细开发规划

### Task #8: 工作台 - 最近候选队列增强

**目标**：让用户更清晰地了解候选币种的潜力

**修改内容**：
```typescript
// apps/web/app/page.tsx
// 当前候选队列卡片改为：

<TerminalCard title="最近候选队列">
  <div className="space-y-2">
    {strategyWorkspace.candidates?.slice(0, 6).map((candidate) => (
      <div key={candidate.symbol} className="flex items-center justify-between p-2 rounded border border-[var(--terminal-border)]/50">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm">{candidate.symbol.replace("USDT", "")}</span>
          <StatusBadge value={candidate.signal_status || "观望"} />
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-[var(--terminal-muted)]">评分: <span className="text-[var(--terminal-cyan)]">{candidate.score?.toFixed(2) || "--"}</span></span>
          <span className="text-[var(--terminal-muted)]">研究: <span className={candidate.research_score > 0.5 ? "text-green-400" : "text-yellow-400"}>{candidate.research_score?.toFixed(2) || "--"}</span></span>
        </div>
      </div>
    ))}
  </div>
</TerminalCard>
```

**API修改**：
- 可能需要扩展 `getStrategyWorkspace` 返回的候选数据结构

---

### Task #1: 工作台 - 入场状态卡片增强

**目标**：提供更完整的入场决策依据

**修改内容**：
```typescript
// apps/web/components/entry-status-card.tsx
// 新增指标显示：

interface EntryCondition {
  symbol: string;
  rsi: number;
  trend: "bullish" | "bearish" | "neutral";
  volume: "high" | "low" | "normal";
  macd: "golden_cross" | "death_cross" | "none";
  score: number;
  reason: string;
}

// 卡片内容改为：
<div className="space-y-3">
  {conditions.map((cond) => (
    <div key={cond.symbol} className="border border-[var(--terminal-border)] rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium">{cond.symbol.replace("USDT", "")}</span>
        <span className="text-xs">评分: {cond.score.toFixed(2)}</span>
      </div>
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="flex flex-col">
          <span className="text-[var(--terminal-muted)]">RSI</span>
          <span className={cond.rsi < 30 ? "text-green-400" : cond.rsi > 70 ? "text-red-400" : ""}>{cond.rsi.toFixed(1)}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[var(--terminal-muted)]">趋势</span>
          <span className={cond.trend === "bullish" ? "text-green-400" : cond.trend === "bearish" ? "text-red-400" : ""}>
            {cond.trend === "bullish" ? "↑看涨" : cond.trend === "bearish" ? "↓看跌" : "→中性"}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[var(--terminal-muted)]">成交量</span>
          <span className={cond.volume === "high" ? "text-green-400" : cond.volume === "low" ? "text-yellow-400" : ""}>
            {cond.volume === "high" ? "放量" : cond.volume === "low" ? "缩量" : "正常"}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[var(--terminal-muted)]">MACD</span>
          <span className={cond.macd === "golden_cross" ? "text-green-400" : cond.macd === "death_cross" ? "text-red-400" : ""}>
            {cond.macd === "golden_cross" ? "金叉" : cond.macd === "death_cross" ? "死叉" : "无信号"}
          </span>
        </div>
      </div>
    </div>
  ))}
</div>
```

**API修改**：
- 扩展 `getRsiSummary` 或新增 `getEntryConditions` API

---

### Task #9: 余额页 - 添加USD估值

**目标**：让用户清楚知道资产总价值

**修改内容**：
```typescript
// apps/web/app/balances/page.tsx
// 新增总价值显示和单资产估值

interface BalanceWithPrice extends BalanceItem {
  usdValue: number;
  price: number;
}

// 新增卡片：
<TerminalCard title="资产总览">
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
    <MetricCard label="总资产价值" value={`$${totalValue.toFixed(2)}`} colorType="positive" />
    <MetricCard label="可交易价值" value={`$${tradableValue.toFixed(2)}`} colorType="neutral" />
    <MetricCard label="Dust价值" value={`$${dustValue.toFixed(2)}`} colorType="neutral" />
    <MetricCard label="资产数量" value={String(items.length)} colorType="neutral" />
  </div>
</TerminalCard>

// 表格添加列：
<th>单价</th>
<th>USD价值</th>
// ...
<td>${item.price.toFixed(4)}</td>
<td>${item.usdValue.toFixed(2)}</td>
```

**API修改**：
- 扩展 `listBalances` 返回价格数据
- 或新增 `getAssetPrices` API

---

### Task #2: 运维页 - 巡检统计增强

**目标**：提供巡检效果的量化指标

**修改内容**：
```typescript
// apps/web/app/ops/page.tsx
// 在巡检控制卡片中添加统计：

<TerminalCard title="巡检统计">
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
    <InfoBlock label="总运行次数" value={String(patrolSchedule.total_runs || 0)} />
    <InfoBlock label="成功率" value={`${((patrolSchedule.success_rate || 0) * 100).toFixed(1)}%`} />
    <InfoBlock label="失败次数" value={String(patrolSchedule.failed_runs || 0)} />
    <InfoBlock label="平均耗时" value={avgDuration ? `${avgDuration.toFixed(1)}s` : "--"} />
  </div>
  {/* 最近失败原因 */}
  {recentFailures.length > 0 && (
    <div className="mt-4">
      <p className="text-xs text-[var(--terminal-muted)] mb-2">最近失败原因：</p>
      <div className="space-y-1">
        {recentFailures.slice(0, 3).map((f, i) => (
          <div key={i} className="text-xs text-red-400">{f.reason}</div>
        ))}
      </div>
    </div>
  )}
</TerminalCard>
```

---

### Task #7: RSI概览 - 筛选功能

**目标**：快速定位目标币种

**修改内容**：
```typescript
// apps/web/components/rsi-summary-card.tsx
// 添加筛选状态和按钮

const [filter, setFilter] = useState<"all" | "overbought" | "oversold" | "neutral">("all");
const [sortBy, setSortBy] = useState<"rsi_asc" | "rsi_desc" | "default">("default");

const filteredItems = items.filter((item) => {
  if (filter === "all") return true;
  return item.state === filter;
}).sort((a, b) => {
  if (sortBy === "rsi_asc") return a.rsi - b.rsi;
  if (sortBy === "rsi_desc") return b.rsi - a.rsi;
  return 0;
});

// 渲染筛选按钮：
<div className="flex gap-2 mb-3">
  {["all", "overbought", "oversold", "neutral"].map((f) => (
    <button
      key={f}
      onClick={() => setFilter(f as typeof filter)}
      className={`px-2 py-1 text-xs rounded ${filter === f ? "bg-[var(--terminal-cyan)]/20 border-[var(--terminal-cyan)]" : "bg-[var(--terminal-border)]/30"}`}
    >
      {f === "all" ? "全部" : f === "overbought" ? "超买" : f === "oversold" ? "超卖" : "中性"}
    </button>
  ))}
  <select
    value={sortBy}
    onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
    className="px-2 py-1 text-xs rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)]"
  >
    <option value="default">默认排序</option>
    <option value="rsi_asc">RSI升序</option>
    <option value="rsi_desc">RSI降序</option>
  </select>
</div>
```

---

### Task #6: 周期历史 - 详情面板优化

**目标**：改善信息可读性

**修改内容**：
```typescript
// apps/web/components/automation-cycle-history-card.tsx
// 使用标签页分组详情

const [activeTab, setActiveTab] = useState<"basic" | "candidates" | "tasks" | "rsi">("basic");

{isExpanded && (
  <div className="px-3 pb-3 pt-2 border-t border-[var(--terminal-border)]/30">
    {/* 标签页导航 */}
    <div className="flex gap-2 mb-3 border-b border-[var(--terminal-border)]/30 pb-2">
      {["basic", "candidates", "tasks", "rsi"].map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab as typeof activeTab)}
          className={`px-2 py-1 text-xs rounded ${activeTab === tab ? "bg-[var(--terminal-cyan)]/20" : ""}`}
        >
          {tab === "basic" ? "基础" : tab === "candidates" ? "候选" : tab === "tasks" ? "任务" : "RSI"}
        </button>
      ))}
    </div>
    
    {/* 标签页内容 */}
    {activeTab === "basic" && <BasicInfo item={item} />}
    {activeTab === "candidates" && <CandidatesInfo item={item} />}
    {activeTab === "tasks" && <TasksInfo item={item} />}
    {activeTab === "rsi" && <RsiInfo item={item} />}
  </div>
)}
```

---

### Task #4: 性能优化 - 合并刷新请求

**目标**：减少API请求次数

**当前问题**：
- DualStrategyCard: 30秒刷新
- EntryStatusCard: 60秒刷新
- RsiSummaryCard: 300秒刷新
- AutomationCycleHistoryCard: 60秒刷新

**优化方案**：
1. 使用统一的数据获取Hook
2. 对相同数据的请求进行去重
3. 考虑使用React Query进行缓存管理

```typescript
// apps/web/hooks/useWorkspaceData.ts
export function useWorkspaceData() {
  const [data, setData] = useState({...});
  
  useEffect(() => {
    const fetchData = async () => {
      // 合并多个API请求
      const [status, rsi, history] = await Promise.all([
        getSystemStatus(),
        getRsiSummary("1d"),
        getAutomationCycleHistory(100),
      ]);
      // ...
    };
    
    fetchData();
    const interval = setInterval(fetchData, 30000); // 统一30秒刷新
    return () => clearInterval(interval);
  }, []);
  
  return data;
}
```

---

## 三、测试规划

### 3.1 单元测试

| 测试项 | 测试内容 |
|--------|----------|
| RSI筛选 | 验证筛选按钮正确过滤数据 |
| 排序功能 | 验证升序降序正确排序 |
| 估值计算 | 验证USD价值计算正确 |
| 统计计算 | 验证成功率、平均耗时计算正确 |

### 3.2 集成测试

| 测试项 | 测试步骤 |
|--------|----------|
| 工作台加载 | 1. 打开首页 2. 验证所有卡片加载 3. 验证数据正确显示 |
| 余额页估值 | 1. 打开余额页 2. 验证价格获取 3. 验证总价值计算 |
| 运维页统计 | 1. 打开运维页 2. 验证统计数据 3. 验证失败原因显示 |
| 周期历史展开 | 1. 点击历史记录 2. 验证标签页切换 3. 验证各标签内容 |

### 3.3 性能测试

| 测试项 | 预期结果 |
|--------|----------|
| 首页加载时间 | < 3秒 |
| API请求数量 | 减少30%以上 |
| 刷新间隔一致性 | 统一30秒 |

### 3.4 兼容性测试

| 测试环境 | 测试内容 |
|----------|----------|
| Chrome | 所有功能正常 |
| Firefox | 所有功能正常 |
| Safari | 所有功能正常 |
| 移动端响应式 | 布局正确适配 |

---

## 四、部署流程

```bash
# 1. 本地提交代码
git add . && git commit -m "feat: 前端优化 - 入场状态增强、余额估值、巡检统计、RSI筛选"
git push

# 2. 服务器部署
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
cd ~/Quant && git pull
cd infra/deploy
docker compose build web && docker compose up -d --no-deps web

# 3. 验证
docker logs quant-web --tail 30
curl http://localhost:9012/

# 4. 检查交易系统
docker logs quant-freqtrade --tail 20
curl http://localhost:9011/api/v1/system/status
```

---

## 五、验证清单

- [ ] 工作台所有卡片正常加载
- [ ] 入场状态显示完整指标
- [ ] 余额页显示USD估值
- [ ] 运维页显示巡检统计
- [ ] RSI筛选功能正常
- [ ] 周期历史标签页切换正常
- [ ] Freqtrade交易正常
- [ ] 自动化周期正常运行

---

## 六、回滚方案

如果出现问题，执行以下回滚：

```bash
# 服务器回滚
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
cd ~/Quant
git log --oneline -5  # 找到上一个稳定版本
git checkout <commit_hash>
cd infra/deploy
docker compose build web && docker compose up -d --no-deps web
```
