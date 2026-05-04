/**
 * 模型 JSON 面板组件
 * 展示模型配置的 JSON 信息
 */
"use client";

/* 模型 JSON 面板属性 */
export type ModelJsonPanelProps = {
  /** JSON 数据对象 */
  data: Record<string, unknown>;
  /** 面板标题 */
  title?: string;
  /** 额外的类名 */
  className?: string;
};

/* 模型 JSON 面板组件 */
export function ModelJsonPanel({
  data,
  title = "模型信息",
  className = "",
}: ModelJsonPanelProps) {
  // 格式化 JSON 字符串
  const jsonString = JSON.stringify(data, null, 2);

  return (
    <div className={`terminal-control-panel ${className}`}>
      {/* 标题 */}
      <div className="terminal-control-panel-title">{title}</div>

      {/* JSON 内容 */}
      <div className="terminal-json-panel">
        <pre className="whitespace-pre-wrap break-all">{jsonString}</pre>
      </div>
    </div>
  );
}
