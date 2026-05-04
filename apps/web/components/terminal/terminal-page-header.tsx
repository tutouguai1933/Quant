/**
 * 终端页面头组件
 * 面包屑、标题、副标题的紧凑展示
 * 高度约 78-92px
 */

/* 页面头属性 */
export type TerminalPageHeaderProps = {
  /** 面包屑路径，如 "研究 / 模型训练" */
  breadcrumb: string;
  /** 页面标题 */
  title: string;
  /** 页面副标题 */
  subtitle: string;
};

/* 终端页面头组件 */
export function TerminalPageHeader({
  breadcrumb,
  title,
  subtitle,
}: TerminalPageHeaderProps) {
  return (
    <header className="terminal-page-header">
      {/* 面包屑 */}
      <div className="terminal-breadcrumb">
        {breadcrumb}
      </div>

      {/* 标题 */}
      <h1 className="terminal-page-title">
        {title}
      </h1>

      {/* 副标题 */}
      {subtitle && (
        <p className="terminal-page-subtitle">
          {subtitle}
        </p>
      )}
    </header>
  );
}
