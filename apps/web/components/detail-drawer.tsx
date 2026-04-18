"use client";

/* 这个文件负责统一右侧详情抽屉，承接摘要卡下钻后的细节信息。 */

import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { cn } from "../lib/utils";
import { Button, type ButtonProps } from "./ui/button";

type DetailDrawerProps = {
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

/* 渲染统一详情抽屉。 */
export function DetailDrawer({
  triggerLabel,
  title,
  description,
  closeLabel = "关闭详情抽屉",
  children,
  footer,
  triggerVariant = "outline",
  triggerSize = "sm",
  className,
}: DetailDrawerProps) {
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
        aria-controls={`${titleId}-drawer`}
      >
        {triggerLabel}
      </Button>

      {open ? (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            aria-label="关闭抽屉遮罩"
            onClick={() => setOpen(false)}
          />

          <div
            id={`${titleId}-drawer`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className={cn(
              "absolute inset-y-0 right-0 flex h-full w-full max-w-xl flex-col border-l border-border/70 bg-card/98 shadow-[-24px_0_60px_rgba(2,6,23,0.45)]",
              className,
            )}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border/60 px-5 py-5">
              <div className="space-y-2">
                <h4 id={titleId} className="text-lg font-semibold tracking-tight text-foreground">
                  {title}
                </h4>
                {description ? <p className="max-w-lg text-sm leading-6 text-muted-foreground">{description}</p> : null}
              </div>
              <Button ref={closeButtonRef} type="button" variant="ghost" size="sm" onClick={() => setOpen(false)} aria-label={closeLabel}>
                <X className="size-4" />
                关闭
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>

            {footer ? <div className="border-t border-border/60 px-5 py-4 text-sm leading-6 text-muted-foreground">{footer}</div> : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
