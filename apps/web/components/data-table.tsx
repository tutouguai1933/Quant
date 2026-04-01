/* 这个文件负责统一渲染表格型数据。 */

import type { ReactNode } from "react";


type DataTableProps = {
  columns: string[];
  rows: Array<{ id: string; cells: ReactNode[] }>;
  emptyTitle: string;
  emptyDetail: string;
};

/* 渲染数据表格。 */
export function DataTable({ columns, rows, emptyTitle, emptyDetail }: DataTableProps) {
  if (!rows.length) {
    return (
      <section className="empty-panel">
        <h3>{emptyTitle}</h3>
        <p>{emptyDetail}</p>
      </section>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {row.cells.map((cell, index) => (
                <td key={`${row.id}-${index}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
