"use client";

/* 这个文件负责给表单提交按钮提供统一的运行中反馈。 */

import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

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
  const [hydrated, setHydrated] = useState(false);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    const currentButton = buttonRef.current;
    const currentForm = currentButton?.form;
    const isSubmitAction = (props.type ?? "submit") === "submit";
    if (!currentButton || !currentForm || !isSubmitAction) {
      return undefined;
    }

    /* 统一覆盖点击和 Enter 提交，确保表单开始提交时就进入运行中。 */
    const handleSubmit = (event: SubmitEvent) => {
      const submitter = event.submitter;
      if (submitter && submitter !== currentButton) {
        return;
      }
      flushSync(() => {
        setPending(true);
      });
    };

    currentForm.addEventListener("submit", handleSubmit);
    return () => {
      currentForm.removeEventListener("submit", handleSubmit);
    };
  }, [props.type]);

  return (
    <div className="space-y-2">
      <Button
        {...props}
        ref={buttonRef}
        data-hydrated={hydrated ? "true" : "false"}
        disabled={disabled || pending}
        onClick={(event) => {
          const currentButton = buttonRef.current;
          const currentForm = currentButton?.form;
          const isSubmitAction = (props.type ?? "submit") === "submit" && currentForm;
          if (isSubmitAction && !pending) {
            event.preventDefault();
            flushSync(() => {
              setPending(true);
            });
            window.setTimeout(() => {
              currentForm?.requestSubmit();
            }, 32);
          } else {
            setPending(true);
          }
          onClick?.(event);
        }}
      >
        {pending ? pendingLabel : idleLabel}
      </Button>
      {pending ? <p className="text-xs leading-5 text-muted-foreground">{pendingHint}</p> : null}
    </div>
  );
}
