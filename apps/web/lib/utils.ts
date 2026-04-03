/* 这个文件提供前端通用样式工具，供 shadcn 风格组件复用。 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/* 合并 className，避免组件变体冲突。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
