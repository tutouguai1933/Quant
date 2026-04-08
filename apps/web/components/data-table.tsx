/* 这个文件负责统一渲染表格型数据。 */

import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

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
      <Card className="bg-card/80">
        <CardHeader>
          <CardTitle>{emptyTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-muted-foreground">{emptyDetail}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden bg-card/80">
      <CardContent className="p-0">
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
      </CardContent>
    </Card>
  );
}
