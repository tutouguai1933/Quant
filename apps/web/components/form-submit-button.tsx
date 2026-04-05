"use client";

/* 这个文件负责给表单提交按钮提供统一的运行中反馈。 */

import { useState } from "react";

import { Button, type ButtonProps } from "./ui/button";

type FormSubmitButtonProps = {
  idleLabel: string;
  pendingLabel?: string;
  pendingHint?: string;
} & Omit<ButtonProps, "children">;

/* 渲染带运行中反馈的提交按钮。 */
export function FormSubmitButton({
  idleLabel,
  pendingLabel = "运行中…",
  pendingHint = "操作已提交，页面正在刷新。",
  disabled,
  onClick,
  ...props
}: FormSubmitButtonProps) {
  const [pending, setPending] = useState(false);

  return (
    <div className="space-y-2">
      <Button
        {...props}
        disabled={disabled || pending}
        onClick={(event) => {
          setPending(true);
          onClick?.(event);
        }}
      >
        {pending ? pendingLabel : idleLabel}
      </Button>
      {pending ? <p className="text-xs leading-5 text-muted-foreground">{pendingHint}</p> : null}
    </div>
  );
}
