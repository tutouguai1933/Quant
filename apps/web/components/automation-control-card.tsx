/* 这个文件负责渲染自动化控制动作卡片，供任务页和策略页共用。 */

import { Card, CardContent } from "./ui/card";
import { FormSubmitButton } from "./form-submit-button";

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
          <FormSubmitButton
            type="submit"
            variant={danger ? "danger" : "terminal"}
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="自动化动作已提交，页面会在状态更新后自动刷新。"
            disabled={disabled}
          />
          {disabled && disabledHint ? <p className="text-xs leading-5 text-muted-foreground">{disabledHint}</p> : null}
        </form>
      </CardContent>
    </Card>
  );
}
