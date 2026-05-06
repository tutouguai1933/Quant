"use client";

/* 专门处理自动化动作表单提交的客户端组件 */

import { useRouter } from "next/navigation";
import { useState } from "react";

type ActionFormProps = {
  action: string;
  returnTo: string;
  label: string;
  variant?: "terminal" | "danger";
  hiddenFields?: Record<string, string>;
  disabled?: boolean;
};

export function ActionForm({
  action,
  returnTo,
  label,
  variant = "terminal",
  hiddenFields = {},
  disabled = false,
}: ActionFormProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || disabled) return;

    setIsSubmitting(true);

    try {
      // 构建 form data
      const formData = new FormData();
      formData.append("action", action);
      formData.append("returnTo", returnTo);
      for (const [name, value] of Object.entries(hiddenFields)) {
        formData.append(name, value);
      }

      // 发送 POST 请求
      const response = await fetch("/actions", {
        method: "POST",
        body: formData,
      });

      // 处理重定向
      if (response.redirected && response.url) {
        const url = new URL(response.url);
        router.push(url.pathname + url.search);
      } else {
        router.push(returnTo);
      }
    } catch (error) {
      console.error("提交失败:", error);
      router.push(`${returnTo}?tone=error&title=操作失败&message=请求失败，请重试`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const baseClass = "px-4 py-2 text-sm rounded font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClass =
    variant === "danger"
      ? "bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
      : "bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)] border border-[var(--terminal-cyan)]/30 hover:bg-[var(--terminal-cyan)]/30";

  return (
    <form onSubmit={handleSubmit}>
      <button type="submit" disabled={disabled || isSubmitting} className={`${baseClass} ${variantClass}`}>
        {isSubmitting ? `${label}中...` : label}
      </button>
    </form>
  );
}
