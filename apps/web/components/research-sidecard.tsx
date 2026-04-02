/* 这个文件负责渲染单币页右侧研究侧卡。 */

import { StatusBadge } from "./status-badge";
import type { ResearchCockpitSummary } from "../lib/api";

type ResearchSidecardProps = {
  cockpit: ResearchCockpitSummary;
  nextStep: string;
};

/* 渲染研究解释和下一步动作侧卡。 */
export function ResearchSidecard({ cockpit, nextStep }: ResearchSidecardProps) {
  const gateStatus = String(cockpit.research_gate.status ?? "unavailable");

  return (
    <aside className="panel research-sidecard">
      <p className="eyebrow">研究侧卡</p>
      <h3>先看研究解释，再决定是否切到策略页</h3>
      <div className="research-highlight">
        <strong>{formatText(cockpit.overlay_summary, "暂无可用信号")}</strong>
        <p>{formatText(cockpit.research_explanation, "研究解释暂时为空。")}</p>
      </div>

      <div className="research-grid">
        <article>
          <span>研究倾向</span>
          <strong>{formatText(cockpit.research_bias, "unavailable")}</strong>
        </article>
        <article>
          <span>推荐策略</span>
          <strong>{formatText(cockpit.recommended_strategy, "none")}</strong>
        </article>
        <article>
          <span>判断信心</span>
          <strong>{formatText(cockpit.confidence, "low")}</strong>
        </article>
        <article>
          <span>研究门控</span>
          <StatusBadge value={gateStatus} />
        </article>
      </div>

      <div className="research-meta">
        <p>模型版本：{formatText(cockpit.model_version, "n/a")}</p>
        <p>生成时间：{formatText(cockpit.generated_at, "n/a")}</p>
        <p>信号点：{String(cockpit.signal_count ?? 0)}</p>
        <p>入场参考：{formatText(cockpit.entry_hint, "n/a")}</p>
        <p>止损参考：{formatText(cockpit.stop_hint, "n/a")}</p>
      </div>

      <p className="research-next-step">下一步：{formatText(nextStep, "先继续观察。")}</p>
    </aside>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
