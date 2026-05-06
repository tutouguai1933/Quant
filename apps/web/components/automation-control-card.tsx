/* 这个文件负责渲染自动化控制动作卡片，供任务页和策略页共用。 */

import { Card, CardContent } from "./ui/card";
import { ActionForm } from "./action-form";

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
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <ActionForm
            action={action}
            returnTo={returnTo}
            label={label}
            variant={danger ? "danger" : "terminal"}
            hiddenFields={hiddenFields}
            disabled={disabled}
          />
          {disabled && disabledHint ? <p className="text-xs leading-5 text-muted-foreground">{disabledHint}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}
