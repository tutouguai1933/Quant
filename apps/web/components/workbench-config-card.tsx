/* 这个文件负责统一工作台配置卡，让各页的可配置区保持同样的结构和动作反馈。 */

import type { ComponentProps, ReactNode } from "react";

import { FormSubmitButton } from "./form-submit-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

type WorkbenchConfigCardProps = {
  title: string;
  description: string;
  scope: "data" | "features" | "research" | "backtest" | "thresholds";
  returnTo: string;
  children: ReactNode;
  disabled?: boolean;
  disabledReason?: string;
};

type ConfigFieldProps = {
  label: string;
  hint: string;
  children: ReactNode;
};

type ConfigCheckboxOption = {
  value: string;
  label: string;
  checked: boolean;
};

/* 渲染统一工作台配置卡。 */
export function WorkbenchConfigCard({
  title,
  description,
  scope,
  returnTo,
  children,
  disabled = false,
  disabledReason = "工作台暂时不可用，先恢复研究接口再保存配置。",
}: WorkbenchConfigCardProps) {
  return (
    <Card className="bg-card/90">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value="update_workbench_config" />
          <input type="hidden" name="section" value={scope} />
          <input type="hidden" name="returnTo" value={returnTo} />
          {disabled ? <p className="text-sm leading-6 text-amber-200">{disabledReason}</p> : null}
          <fieldset disabled={disabled} className="grid gap-4 disabled:opacity-60">
            {children}
          </fieldset>
          <FormSubmitButton
            type="submit"
            size="sm"
            idleLabel="保存当前配置"
            pendingLabel="保存中…"
            pendingHint="配置已提交，当前工作台和后续研究链会按新配置刷新。"
            disabled={disabled}
          />
        </form>
      </CardContent>
    </Card>
  );
}

/* 渲染统一字段块。 */
export function ConfigField({ label, hint, children }: ConfigFieldProps) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/10 p-4">
      <div className="mb-3">
        <p className="eyebrow">{label}</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{hint}</p>
      </div>
      <div className="grid gap-3">{children}</div>
    </div>
  );
}

/* 渲染统一输入框。 */
export function ConfigInput(props: ComponentProps<typeof Input>) {
  return <Input {...props} className={["bg-background/50", props.className].filter(Boolean).join(" ")} />;
}

/* 渲染统一下拉框。 */
export function ConfigSelect({
  name,
  options,
  defaultValue,
}: {
  name: string;
  options: Array<{ value: string; label: string }>;
  defaultValue: string;
}) {
  return (
    <select
      name={name}
      defaultValue={defaultValue}
      className="flex h-11 w-full rounded-xl border border-border/70 bg-background/70 px-3 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {!options.length ? (
        <option value={defaultValue || ""}>{defaultValue || "当前暂无可选项"}</option>
      ) : null}
      {options.map((item) => (
        <option key={item.value} value={item.value}>
          {item.label}
        </option>
      ))}
    </select>
  );
}

/* 渲染统一多选项。 */
export function ConfigCheckboxGrid({
  name,
  options,
}: {
  name: string;
  options: ConfigCheckboxOption[];
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <input type="hidden" name={`__present__${name}`} value="1" />
      {options.map((item) => (
        <label
          key={`${name}-${item.value}`}
          className="flex items-center gap-3 rounded-xl border border-border/60 bg-background/45 px-3 py-3 text-sm leading-5 text-foreground"
        >
          <input
            type="checkbox"
            name={name}
            value={item.value}
            defaultChecked={item.checked}
            className="h-4 w-4 rounded border border-border/70 bg-background/70 text-primary"
          />
          <span className="break-all">{item.label}</span>
        </label>
      ))}
    </div>
  );
}
