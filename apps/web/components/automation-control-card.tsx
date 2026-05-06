/* 这个文件负责渲染自动化控制动作卡片，供任务页和策略页共用。 */

import { Card, CardContent } from "./ui/card";

type AutomationControlCardProps = {
  action: string;
  label: string;
  detail: string;
  returnTo: string;
  danger?: boolean;
  hiddenFields?: Record<string, string>;
  disabled?: boolean;
  disabledHint?: string;
};

export function AutomationControlCard({
  action,
  label,
  detail,
  returnTo,
  danger = false,
  hiddenFields = {},
  disabled = false,
  disabledHint = "",
}: AutomationControlCardProps) {
  return (
    <Card className={danger ? "border-rose-500/30 bg-rose-500/10" : "bg-[color:var(--panel-strong)]/80"}>
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value={returnTo} />
          {Object.entries(hiddenFields).map(([name, value]) => (
            <input key={name} type="hidden" name={name} value={value} />
          ))}
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <button
            type="submit"
            disabled={disabled}
            className={`px-4 py-2 text-sm rounded font-medium transition-colors ${
              danger
                ? "bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
                : "bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)] border border-[var(--terminal-cyan)]/30 hover:bg-[var(--terminal-cyan)]/30"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {label}
          </button>
          {disabled && disabledHint ? <p className="text-xs leading-5 text-muted-foreground">{disabledHint}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}
