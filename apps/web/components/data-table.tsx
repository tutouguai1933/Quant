/* 这个文件负责统一渲染表格型数据。 */

import type { ReactNode } from "react";

import { TerminalCard } from "./terminal/terminal-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

type DataTableProps = {
  columns: string[];
  rows: Array<{ id: string; cells: ReactNode[] }>;
  emptyTitle: string;
  emptyDetail: string;
  emptyEyebrow?: string;
};

/* 渲染数据表格。 */
export function DataTable({ columns, rows, emptyTitle, emptyDetail, emptyEyebrow }: DataTableProps) {
  if (!rows.length) {
    return (
      <TerminalCard title={emptyTitle}>
        {emptyEyebrow ? <p className="eyebrow">{emptyEyebrow}</p> : null}
        <p className="text-sm leading-6 text-muted-foreground">{emptyDetail}</p>
      </TerminalCard>
    );
  }

  return (
    <TerminalCard className="overflow-hidden">
      <div className="-m-4">
        <Table className="table-fixed">
          <TableHeader className="bg-muted/20">
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column}>{column}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="align-top">
                {row.cells.map((cell, index) => (
                  <TableCell key={`${row.id}-${index}`}>{cell}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TerminalCard>
  );
}
