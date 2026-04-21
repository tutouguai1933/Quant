"use client";

import { useState } from "react";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

type ConfirmDialogProps = {
  action: string;
  label: string;
  riskLevel: "safe" | "medium" | "danger" | "critical";
  onConfirm: () => void;
  onCancel: () => void;
};

export function OpenclawActionConfirmDialog({ action, label, riskLevel, onConfirm, onCancel }: ConfirmDialogProps) {
  const [confirmText, setConfirmText] = useState("");
  const [isConfirming, setIsConfirming] = useState(false);

  // 根据风险等级确定确认要求
  const getConfirmRequirement = () => {
    switch (riskLevel) {
      case "safe":
        return { requireInput: false, hintText: "" };
      case "medium":
        return { requireInput: true, hintText: "输入 CONFIRM 确认" };
      case "danger":
        return { requireInput: true, hintText: `输入 ${action} 确认` };
      case "critical":
        return { requireInput: true, hintText: "此动作被禁止" };
    }
  };

  const requirement = getConfirmRequirement();
  const canConfirm = !requirement.requireInput || confirmText === (riskLevel === "medium" ? "CONFIRM" : action);

  return (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle>确认执行: {label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {riskLevel !== "critical" && (
          <>
            {requirement.requireInput && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">{requirement.hintText}</p>
                <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder={requirement.hintText} />
              </div>
            )}
            <div className="flex gap-3">
              <Button variant="danger" disabled={!canConfirm || isConfirming} onClick={() => { setIsConfirming(true); onConfirm(); }}>
                {isConfirming ? "执行中..." : "确认执行"}
              </Button>
              <Button variant="outline" onClick={onCancel}>取消</Button>
            </div>
          </>
        )}
        {riskLevel === "critical" && (
          <p className="text-sm text-destructive">此动作被系统禁止，无法执行。</p>
        )}
      </CardContent>
    </Card>
  );
}