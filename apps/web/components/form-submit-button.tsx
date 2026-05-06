"use client";

/* 这个文件负责给表单提交按钮提供统一的运行中反馈。 */

import { useEffect, useRef, useState } from "react";

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
  ...props
}: FormSubmitButtonProps) {
  const [pending, setPending] = useState(false);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const currentButton = buttonRef.current;
    const currentForm = currentButton?.form;
    if (!currentButton || !currentForm) {
      return undefined;
    }

    /* 监听表单提交事件，显示运行中状态。 */
    const handleSubmit = () => {
      setPending(true);
    };

    currentForm.addEventListener("submit", handleSubmit);
    return () => {
      currentForm.removeEventListener("submit", handleSubmit);
    };
  }, []);

  return (
    <div className="space-y-2">
      <Button
        {...props}
        ref={buttonRef}
        type="submit"
        disabled={disabled || pending}
      >
        {pending ? pendingLabel : idleLabel}
      </Button>
      {pending ? <p className="text-xs leading-5 text-muted-foreground">{pendingHint}</p> : null}
    </div>
  );
}
