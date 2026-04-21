"use client";

/* 这个文件负责统一详情弹窗，承接需要集中对比的细节信息。 */

import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { cn } from "../lib/utils";
import { Button, type ButtonProps } from "./ui/button";

type DetailDialogProps = {
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

/* 渲染统一详情弹窗。 */
export function DetailDialog({
  triggerLabel,
  title,
  description,
  closeLabel = "关闭详情弹窗",
  children,
  footer,
  triggerVariant = "outline",
  triggerSize = "sm",
  className,
}: DetailDialogProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const hadOpenedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    requestAnimationFrame(() => closeButtonRef.current?.focus());
    hadOpenedRef.current = true;

    return () => {
      document.body.style.overflow = previousOverflow;
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
        aria-controls={`${titleId}-dialog`}
      >
        {triggerLabel}
      </Button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
          <button
            type="button"
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            aria-label="关闭弹窗遮罩"
            onClick={() => setOpen(false)}
          />

          <div
            id={`${titleId}-dialog`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={cn(
              "relative z-10 flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-border/70 bg-card/95 shadow-[0_24px_80px_rgba(2,6,23,0.45)]",
              className,
            )}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border/60 px-5 py-4">
              <div className="space-y-2">
                <h4 id={titleId} className="text-lg font-semibold tracking-tight text-foreground">
                  {title}
                </h4>
                {description ? <p className="text-sm leading-6 text-muted-foreground">{description}</p> : null}
              </div>
              <Button ref={closeButtonRef} type="button" variant="ghost" size="sm" onClick={() => setOpen(false)} aria-label={closeLabel}>
                <X className="size-4" />
                关闭
              </Button>
            </div>

            <div className="overflow-y-auto px-5 py-4">{children}</div>

            {footer ? <div className="border-t border-border/60 px-5 py-4 text-sm leading-6 text-muted-foreground">{footer}</div> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
