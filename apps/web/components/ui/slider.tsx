/* Slider组件 - 用于数值调节 */
"use client";

import * as React from "react";

export type SliderProps = {
  value?: number[];
  defaultValue?: number[];
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  onValueChange?: (value: number[]) => void;
  className?: string;
};

export function Slider({
  value,
  defaultValue = [0],
  min = 0,
  max = 100,
  step = 1,
  disabled = false,
  onValueChange,
  className = "",
}: SliderProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue[0]);
  const currentValue = value !== undefined ? value[0] : internalValue;
  const percentage = ((currentValue - min) / (max - min)) * 100;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseFloat(e.target.value);
    if (value === undefined) {
      setInternalValue(newValue);
    }
    if (onValueChange) {
      onValueChange([newValue]);
    }
  };

  return (
    <div className={`relative w-full ${className}`}>
      {/* 背景轨道 */}
      <div className="relative h-2 w-full rounded-full bg-muted/40">
        {/* 已选择区域 */}
        <div
          className="absolute h-full rounded-full bg-primary transition-all duration-100"
          style={{ width: `${percentage}%` }}
        />
      </div>
      {/* 滑块输入 */}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={currentValue}
        disabled={disabled}
        onChange={handleChange}
        className="absolute inset-0 w-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
      />
      {/* 可见滑块指示器 */}
      <div
        className="absolute top-1/2 size-4 -translate-y-1/2 rounded-full border-2 border-primary bg-background shadow-sm transition-all duration-100 pointer-events-none"
        style={{ left: `calc(${percentage}% - 8px)` }}
      />
    </div>
  );
}