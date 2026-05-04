#!/usr/bin/env python3
"""回测结果可视化脚本。

使用Plotly生成以下图表：
- 收益曲线图（时间-累计收益）
- 持仓分布图（交易对-盈亏）
- 月度收益柱状图
- 胜率饼图

Usage:
    python scripts/backtest_visualization.py [backtest_result.zip]
    python scripts/backtest_visualization.py  # 使用最新结果
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BACKTEST_RESULTS_DIR = PROJECT_ROOT / "infra" / "freqtrade" / "user_data" / "backtest_results"
REPORTS_DIR = PROJECT_ROOT / "reports"


def find_latest_backtest() -> Path | None:
    """查找最新的回测结果文件。"""
    if not BACKTEST_RESULTS_DIR.exists():
        return None

    # 检查 .last_result.json
    last_result_file = BACKTEST_RESULTS_DIR / ".last_result.json"
    if last_result_file.exists():
        with open(last_result_file) as f:
            last_result = json.load(f)
            latest_zip = last_result.get("latest_backtest")
            if latest_zip:
                zip_path = BACKTEST_RESULTS_DIR / latest_zip
                if zip_path.exists():
                    return zip_path

    # 回退：按修改时间查找最新的zip文件
    zip_files = list(BACKTEST_RESULTS_DIR.glob("backtest-result-*.zip"))
    if not zip_files:
        return None

    return max(zip_files, key=lambda p: p.stat().st_mtime)


def load_backtest_result(zip_path: Path) -> dict[str, Any]:
    """从zip文件加载回测结果。"""
    with zipfile.ZipFile(zip_path, "r") as z:
        # 查找主结果文件
        result_files = [n for n in z.namelist() if n.endswith(".json") and "_config" not in n and "EnhancedStrategy" not in n]
        if not result_files:
            raise ValueError(f"No result JSON found in {zip_path}")

        with z.open(result_files[0]) as f:
            return json.load(f)


def extract_trades(backtest_data: dict[str, Any]) -> pd.DataFrame:
    """提取交易数据为DataFrame。"""
    strategies = backtest_data.get("strategy", {})
    if not strategies:
        return pd.DataFrame()

    # 取第一个策略的数据
    strategy_name = list(strategies.keys())[0]
    trades = strategies[strategy_name].get("trades", [])

    if not trades:
        return pd.DataFrame()

    df = pd.DataFrame(trades)

    # 转换日期时间
    df["open_date"] = pd.to_datetime(df["open_date"])
    df["close_date"] = pd.to_datetime(df["close_date"])

    return df


def extract_metrics(backtest_data: dict[str, Any]) -> dict[str, Any]:
    """提取回测指标。"""
    strategies = backtest_data.get("strategy", {})
    if not strategies:
        return {}

    strategy_name = list(strategies.keys())[0]
    strat_data = strategies[strategy_name]

    return {
        "total_trades": strat_data.get("total_trades", 0),
        "profit_total": strat_data.get("profit_total", 0),  # 总收益率 %
        "profit_total_abs": strat_data.get("profit_total_abs", 0),  # 绝对收益
        "profit_mean": strat_data.get("profit_mean", 0),  # 平均收益
        "best_pair": strat_data.get("best_pair", ""),
        "worst_pair": strat_data.get("worst_pair", ""),
        "results_per_pair": strat_data.get("results_per_pair", []),
    }


def generate_profit_curve(trades_df: pd.DataFrame, output_dir: Path) -> str:
    """生成收益曲线图。"""
    if trades_df.empty:
        # 生成空图表
        fig = go.Figure()
        fig.add_annotation(text="无交易数据", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="收益曲线")
    else:
        # 按关闭日期排序并计算累计收益
        df = trades_df.sort_values("close_date").copy()
        df["cumulative_profit"] = df["profit_ratio"].cumsum() * 100  # 转换为百分比

        fig = go.Figure()

        # 收益曲线
        fig.add_trace(go.Scatter(
            x=df["close_date"],
            y=df["cumulative_profit"],
            mode="lines+markers",
            name="累计收益 (%)",
            line=dict(color="#2ecc71", width=2),
            marker=dict(size=6),
        ))

        # 添加单笔收益柱状图
        fig.add_trace(go.Bar(
            x=df["close_date"],
            y=df["profit_ratio"] * 100,
            name="单笔收益 (%)",
            marker_color=df["profit_ratio"].apply(lambda x: "#27ae60" if x >= 0 else "#e74c3c"),
            opacity=0.3,
            yaxis="y2",
        ))

        fig.update_layout(
            title="收益曲线",
            xaxis_title="日期",
            yaxis_title="累计收益 (%)",
            yaxis2=dict(title="单笔收益 (%)", overlaying="y", side="right"),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

    output_path = output_dir / "profit_curve.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return str(output_path)


def generate_pair_distribution(trades_df: pd.DataFrame, output_dir: Path) -> str:
    """生成持仓分布图（交易对-盈亏）。"""
    if trades_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无交易数据", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="交易对盈亏分布")
    else:
        # 按交易对聚合
        pair_summary = trades_df.groupby("pair").agg({
            "profit_ratio": "sum",
            "profit_abs": "sum",
            "pair": "count",
        }).rename(columns={"pair": "trade_count"}).reset_index()

        pair_summary["profit_pct"] = pair_summary["profit_ratio"] * 100
        pair_summary = pair_summary.sort_values("profit_pct", ascending=True)

        fig = go.Figure()

        colors = ["#27ae60" if p >= 0 else "#e74c3c" for p in pair_summary["profit_pct"]]

        fig.add_trace(go.Bar(
            x=pair_summary["profit_pct"],
            y=pair_summary["pair"],
            orientation="h",
            marker_color=colors,
            text=[f"{p:.2f}% ({c}笔)" for p, c in zip(pair_summary["profit_pct"], pair_summary["trade_count"])],
            textposition="auto",
        ))

        fig.update_layout(
            title="交易对盈亏分布",
            xaxis_title="累计收益率 (%)",
            yaxis_title="交易对",
            height=max(400, len(pair_summary) * 30),
        )

    output_path = output_dir / "pair_distribution.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return str(output_path)


def generate_monthly_returns(trades_df: pd.DataFrame, output_dir: Path) -> str:
    """生成月度收益柱状图。"""
    if trades_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无交易数据", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="月度收益")
    else:
        # 按月聚合
        df = trades_df.copy()
        # 转换为timezone-naive以避免Period转换警告
        df["close_date"] = df["close_date"].dt.tz_localize(None)
        df["month"] = df["close_date"].dt.to_period("M").astype(str)

        monthly = df.groupby("month").agg({
            "profit_ratio": "sum",
            "profit_abs": "sum",
            "pair": "count",
        }).rename(columns={"pair": "trades"}).reset_index()

        monthly["profit_pct"] = monthly["profit_ratio"] * 100

        fig = go.Figure()

        colors = ["#27ae60" if p >= 0 else "#e74c3c" for p in monthly["profit_pct"]]

        fig.add_trace(go.Bar(
            x=monthly["month"],
            y=monthly["profit_pct"],
            marker_color=colors,
            text=[f"{p:.2f}%<br>({t}笔)" for p, t in zip(monthly["profit_pct"], monthly["trades"])],
            textposition="auto",
        ))

        fig.update_layout(
            title="月度收益",
            xaxis_title="月份",
            yaxis_title="收益率 (%)",
            xaxis=dict(tickangle=-45),
        )

    output_path = output_dir / "monthly_returns.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return str(output_path)


def generate_win_rate_pie(trades_df: pd.DataFrame, output_dir: Path) -> str:
    """生成胜率饼图。"""
    if trades_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无交易数据", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="胜率统计")
    else:
        wins = (trades_df["profit_ratio"] > 0).sum()
        losses = (trades_df["profit_ratio"] <= 0).sum()
        total = len(trades_df)
        win_rate = wins / total * 100 if total > 0 else 0

        fig = go.Figure()

        fig.add_trace(go.Pie(
            labels=["盈利", "亏损"],
            values=[wins, losses],
            marker_colors=["#27ae60", "#e74c3c"],
            textinfo="label+percent+value",
            texttemplate="<b>%{label}</b><br>%{value}笔<br>%{percent}",
            hole=0.4,
        ))

        fig.update_layout(
            title=f"胜率统计 (胜率: {win_rate:.1f}%)",
            annotations=[dict(text=f"{total}<br>笔", x=0.5, y=0.5, font_size=20, showarrow=False)],
        )

    output_path = output_dir / "win_rate_pie.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return str(output_path)


def generate_combined_dashboard(trades_df: pd.DataFrame, metrics: dict[str, Any], output_dir: Path) -> str:
    """生成综合仪表板。"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("收益曲线", "交易对盈亏分布", "月度收益", "胜率统计"),
        specs=[
            [{"type": "scatter"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "pie"}],
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.1,
    )

    if trades_df.empty:
        # 添加"无数据"提示
        for row in range(1, 3):
            for col in range(1, 3):
                fig.add_annotation(text="无交易数据", xref=f"x{row*2+col}", yref=f"y{row}", row=row, col=col)
    else:
        # 1. 收益曲线
        df = trades_df.sort_values("close_date").copy()
        df["cumulative_profit"] = df["profit_ratio"].cumsum() * 100

        fig.add_trace(
            go.Scatter(
                x=df["close_date"],
                y=df["cumulative_profit"],
                mode="lines+markers",
                name="累计收益 (%)",
                line=dict(color="#2ecc71", width=2),
            ),
            row=1, col=1,
        )

        # 2. 交易对分布
        pair_summary = trades_df.groupby("pair").agg({"profit_ratio": "sum"}).reset_index()
        pair_summary["profit_pct"] = pair_summary["profit_ratio"] * 100
        pair_summary = pair_summary.sort_values("profit_pct", ascending=True).tail(10)

        colors = ["#27ae60" if p >= 0 else "#e74c3c" for p in pair_summary["profit_pct"]]
        fig.add_trace(
            go.Bar(
                x=pair_summary["profit_pct"],
                y=pair_summary["pair"],
                orientation="h",
                marker_color=colors,
                name="收益率",
            ),
            row=1, col=2,
        )

        # 3. 月度收益
        # 转换为timezone-naive以避免Period转换警告
        df["close_date"] = df["close_date"].dt.tz_localize(None)
        df["month"] = df["close_date"].dt.to_period("M").astype(str)
        monthly = df.groupby("month")["profit_ratio"].sum().reset_index()
        monthly["profit_pct"] = monthly["profit_ratio"] * 100

        colors_monthly = ["#27ae60" if p >= 0 else "#e74c3c" for p in monthly["profit_pct"]]
        fig.add_trace(
            go.Bar(
                x=monthly["month"],
                y=monthly["profit_pct"],
                marker_color=colors_monthly,
                name="月收益",
            ),
            row=2, col=1,
        )

        # 4. 胜率饼图
        wins = (trades_df["profit_ratio"] > 0).sum()
        losses = (trades_df["profit_ratio"] <= 0).sum()

        fig.add_trace(
            go.Pie(
                labels=["盈利", "亏损"],
                values=[wins, losses],
                marker_colors=["#27ae60", "#e74c3c"],
                name="胜率",
                hole=0.4,
            ),
            row=2, col=2,
        )

    # 更新布局
    total_trades = metrics.get("total_trades", len(trades_df))
    total_return = metrics.get("profit_total", 0)

    fig.update_layout(
        title_text=f"回测结果仪表板 - 总交易: {total_trades}笔 | 总收益: {total_return:.2f}%",
        title_x=0.5,
        height=800,
        showlegend=False,
    )

    fig.update_xaxes(title_text="日期", row=1, col=1)
    fig.update_yaxes(title_text="累计收益 (%)", row=1, col=1)
    fig.update_xaxes(title_text="收益率 (%)", row=1, col=2)
    fig.update_xaxes(title_text="月份", row=2, col=1)
    fig.update_yaxes(title_text="收益率 (%)", row=2, col=1)

    output_path = output_dir / "dashboard.html"
    fig.write_html(output_path, include_plotlyjs="cdn")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="回测结果可视化")
    parser.add_argument(
        "backtest_file",
        nargs="?",
        help="回测结果zip文件路径（默认使用最新结果）",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=str(REPORTS_DIR),
        help=f"输出目录（默认: {REPORTS_DIR}）",
    )

    args = parser.parse_args()

    # 确定回测文件
    if args.backtest_file:
        zip_path = Path(args.backtest_file)
        if not zip_path.exists():
            print(f"错误: 文件不存在: {zip_path}")
            sys.exit(1)
    else:
        zip_path = find_latest_backtest()
        if not zip_path:
            print("错误: 未找到回测结果文件")
            sys.exit(1)

    print(f"使用回测结果: {zip_path}")

    # 加载数据
    backtest_data = load_backtest_result(zip_path)
    trades_df = extract_trades(backtest_data)
    metrics = extract_metrics(backtest_data)

    print(f"加载 {len(trades_df)} 条交易记录")

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成图表
    results = []
    results.append(("收益曲线图", generate_profit_curve(trades_df, output_dir)))
    results.append(("持仓分布图", generate_pair_distribution(trades_df, output_dir)))
    results.append(("月度收益图", generate_monthly_returns(trades_df, output_dir)))
    results.append(("胜率饼图", generate_win_rate_pie(trades_df, output_dir)))
    results.append(("综合仪表板", generate_combined_dashboard(trades_df, metrics, output_dir)))

    print("\n生成的图表:")
    for name, path in results:
        print(f"  - {name}: {path}")

    print("\n可视化完成!")


if __name__ == "__main__":
    main()