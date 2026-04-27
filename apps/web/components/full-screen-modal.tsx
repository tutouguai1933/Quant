"use client";

/* 这个文件负责全屏弹窗，用于配置页面展示大量配置项。 */

import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { cn } from "../lib/utils";
import { Button, type ButtonProps } from "./ui/button";

type FullScreenModalProps = {
  triggerLabel: string;
  title: string;
  description?: string;
  closeLabel?: string;
  children: ReactNode;
  footer?: ReactNode;
  triggerVariant?: ButtonProps["variant"];
  triggerSize?: ButtonProps["size"];
  className?: string;
};

/* 渲染全屏弹窗，背景模糊，内容区域居中显示。 */
export function FullScreenModal({
  triggerLabel,
  title,
  description,
  closeLabel = "关闭弹窗",
  children,
  footer,
  triggerVariant = "outline",
  triggerSize = "sm",
  className,
}: FullScreenModalProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const hadOpenedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    requestAnimationFrame(() => closeButtonRef.current?.focus());
    hadOpenedRef.current = true;

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open && hadOpenedRef.current) {
      triggerRef.current?.focus();
      hadOpenedRef.current = false;
    }
  }, [open]);

  return (
    <>
      <Button
        ref={triggerRef}
        type="button"
        variant={triggerVariant}
        size={triggerSize}
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-controls={`${titleId}-modal`}
      >
        {triggerLabel}
      </Button>

      {open ? (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          {/* 背景：完全模糊，覆盖所有内容 */}
          <div
            className="absolute inset-0 bg-background/80 backdrop-blur-xl"
            aria-hidden="true"
          />

          {/* 弹窗内容：居中，最大宽度 1200px，高度最大 90vh，确保在背景之上 */}
          <div
            id={`${titleId}-modal`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={cn(
              "relative z-[10000] flex max-h-[90vh] w-full max-w-[1200px] flex-col rounded-2xl border border-border/70 bg-card shadow-[0_24px_60px_rgba(2,6,23,0.45)]",
              className,
            )}
          >
            {/* 头部 */}
            <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border/60 px-6 py-5">
              <div className="space-y-2">
                <h4 id={titleId} className="text-xl font-semibold tracking-tight text-foreground">
                  {title}
                </h4>
                {description ? <p className="text-sm leading-6 text-muted-foreground">{description}</p> : null}
              </div>
              <Button ref={closeButtonRef} type="button" variant="ghost" size="sm" onClick={() => setOpen(false)} aria-label={closeLabel}>
                <X className="size-4" />
                关闭
              </Button>
            </div>

            {/* 内容区域：可滚动 */}
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>

            {/* 底部 */}
            {footer ? <div className="shrink-0 border-t border-border/60 px-6 py-4 text-sm leading-6 text-muted-foreground">{footer}</div> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}