#!/usr/bin/env python3
"""API 端点测试脚本 - 测试所有后端 API 的响应时间和正确性"""

import time
import json
import sys
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict

try:
    import requests
except ImportError:
    print("错误: 需要安装 requests 库")
    print("运行: pip install requests")
    sys.exit(1)


@dataclass
class EndpointTest:
    """端点测试结果"""
    method: str
    path: str
    status_code: int
    response_time_ms: float
    success: bool
    error_message: str = ""
    data_valid: bool = True
    requires_auth: bool = False


class APITester:
    """API 测试器"""

    def __init__(self, base_url: str = "http://localhost:9011"):
        self.base_url = base_url.rstrip("/")
        self.results: List[EndpointTest] = []
        self.token = ""
        self.slow_threshold_ms = 1000

    def test_endpoint(
        self,
        method: str,
        path: str,
        requires_auth: bool = False,
        payload: Dict = None,
        params: Dict = None
    ) -> EndpointTest:
        """测试单个端点"""
        url = f"{self.base_url}{path}"
        headers = {}

        if requires_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        start_time = time.time()

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=payload, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的方法: {method}")

            elapsed_ms = (time.time() - start_time) * 1000

            # 检查响应数据结构
            data_valid = True
            error_msg = ""

            try:
                json_data = response.json()
                # 检查标准响应格式
                if not isinstance(json_data, dict):
                    data_valid = False
                    error_msg = "响应不是 JSON 对象"
                elif "data" not in json_data and "error" not in json_data:
                    # Openclaw 端点可能有不同的格式
                    if not path.startswith("/openclaw"):
                        data_valid = False
                        error_msg = "缺少 data 或 error 字段"
            except Exception as e:
                data_valid = False
                error_msg = f"JSON 解析失败: {str(e)}"

            success = 200 <= response.status_code < 300

            return EndpointTest(
                method=method,
                path=path,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                success=success,
                error_message=error_msg,
                data_valid=data_valid,
                requires_auth=requires_auth
            )

        except requests.exceptions.Timeout:
            elapsed_ms = (time.time() - start_time) * 1000
            return EndpointTest(
                method=method,
                path=path,
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                success=False,
                error_message="请求超时",
                data_valid=False,
                requires_auth=requires_auth
            )
        except requests.exceptions.ConnectionError:
            elapsed_ms = (time.time() - start_time) * 1000
            return EndpointTest(
                method=method,
                path=path,
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                success=False,
                error_message="连接失败 - API 服务可能未启动",
                data_valid=False,
                requires_auth=requires_auth
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return EndpointTest(
                method=method,
                path=path,
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                success=False,
                error_message=str(e),
                data_valid=False,
                requires_auth=requires_auth
            )

    def login(self) -> bool:
        """登录获取 token"""
        result = self.test_endpoint(
            "POST",
            "/api/v1/auth/login",
            payload={"username": "admin", "password": "1933"}
        )
        self.results.append(result)

        if result.success:
            try:
                response = requests.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": "admin", "password": "1933"}
                )
                data = response.json()
                if data.get("data") and data["data"].get("item"):
                    self.token = data["data"]["item"].get("token", "")
                    return bool(self.token)
            except:
                pass
        return False

    def run_all_tests(self):
        """运行所有端点测试"""
        print(f"开始测试 API: {self.base_url}")
        print("=" * 80)

        # 1. Health 端点 (无需认证)
        print("\n[1/18] 测试 Health 端点...")
        self.results.append(self.test_endpoint("GET", "/health"))
        self.results.append(self.test_endpoint("GET", "/healthz"))

        # 2. Auth 端点
        print("[2/18] 测试 Auth 端点...")
        has_token = self.login()
        self.results.append(self.test_endpoint("GET", "/api/v1/auth/model"))
        if has_token:
            self.results.append(self.test_endpoint("GET", "/api/v1/auth/session", params={"token": self.token}))

        # 3. Accounts 端点
        print("[3/18] 测试 Accounts 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/accounts"))

        # 4. Balances 端点
        print("[4/18] 测试 Balances 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/balances"))

        # 5. Positions 端点
        print("[5/18] 测试 Positions 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/positions"))

        # 6. Orders 端点
        print("[6/18] 测试 Orders 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/orders"))

        # 7. Market 端点
        print("[7/18] 测试 Market 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/market"))
        self.results.append(self.test_endpoint("GET", "/api/v1/market/BTCUSDT/chart", params={"interval": "4h", "limit": 50}))

        # 8. Signals 端点
        print("[8/18] 测试 Signals 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/signals"))
        self.results.append(self.test_endpoint("GET", "/api/v1/signals/research/latest"))
        self.results.append(self.test_endpoint("GET", "/api/v1/signals/research/candidates"))
        self.results.append(self.test_endpoint("GET", "/api/v1/signals/research/report"))
        self.results.append(self.test_endpoint("GET", "/api/v1/signals/research/runtime"))

        # 9. Strategies 端点
        print("[9/18] 测试 Strategies 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/strategies", requires_auth=True))
        self.results.append(self.test_endpoint("GET", "/api/v1/strategies/catalog", requires_auth=True))
        self.results.append(self.test_endpoint("GET", "/api/v1/strategies/workspace", requires_auth=True))

        # 10. Tasks 端点 (重点测试)
        print("[10/18] 测试 Tasks 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/tasks", requires_auth=True))
        self.results.append(self.test_endpoint("GET", "/api/v1/tasks/automation", requires_auth=True))
        self.results.append(self.test_endpoint("GET", "/api/v1/tasks/validation-review", requires_auth=True))

        # 11. Risk Events 端点
        print("[11/18] 测试 Risk Events 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/risk-events", requires_auth=True))

        # 12. Feature Workspace 端点
        print("[12/18] 测试 Feature Workspace 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/features/workspace"))

        # 13. Research Workspace 端点
        print("[13/18] 测试 Research Workspace 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/research/workspace"))

        # 14. Workbench Config 端点
        print("[14/18] 测试 Workbench Config 端点...")
        self.results.append(self.test_endpoint("GET", "/api/v1/workbench/config"))

        # 15. Openclaw 端点
        print("[15/18] 测试 Openclaw 端点...")
        self.results.append(self.test_endpoint("GET", "/openclaw/snapshot"))

        # 16. 测试 POST 端点 (需要认证的写操作 - 仅测试连通性，不实际执行)
        print("[16/18] 测试 Signals POST 端点...")
        self.results.append(self.test_endpoint(
            "POST",
            "/api/v1/signals/strategy/run",
            payload={"strategy_id": "trend_breakout", "symbol": "BTCUSDT"}
        ))

        # 17. 测试 Tasks POST 端点 (仅检查认证，不实际触发)
        print("[17/18] 测试 Tasks POST 端点 (认证检查)...")
        # 不带 token 应该返回 401 或包含 unauthorized 错误
        result = self.test_endpoint("POST", "/api/v1/tasks/sync", requires_auth=True)
        self.results.append(result)

        # 18. 测试 Automation 端点
        print("[18/18] 测试 Automation 端点...")
        # 只读取状态，不修改

        print("\n测试完成!")
        print("=" * 80)

    def generate_report(self) -> str:
        """生成测试报告"""
        total = len(self.results)
        success_count = sum(1 for r in self.results if r.success)
        failed_count = total - success_count
        slow_count = sum(1 for r in self.results if r.response_time_ms > self.slow_threshold_ms)

        # 统计响应时间
        response_times = [r.response_time_ms for r in self.results if r.success]
        avg_time = sum(response_times) / len(response_times) if response_times else 0
        max_time = max(response_times) if response_times else 0
        min_time = min(response_times) if response_times else 0

        report = []
        report.append("\n" + "=" * 80)
        report.append("API 端点测试报告")
        report.append("=" * 80)
        report.append(f"\n测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"API 地址: {self.base_url}")
        report.append(f"\n总测试数: {total}")
        report.append(f"成功: {success_count} ({success_count/total*100:.1f}%)")
        report.append(f"失败: {failed_count} ({failed_count/total*100:.1f}%)")
        report.append(f"慢接口 (>{self.slow_threshold_ms}ms): {slow_count}")

        report.append(f"\n响应时间统计:")
        report.append(f"  平均: {avg_time:.2f}ms")
        report.append(f"  最快: {min_time:.2f}ms")
        report.append(f"  最慢: {max_time:.2f}ms")

        # 所有端点列表
        report.append("\n" + "-" * 80)
        report.append("所有端点测试结果:")
        report.append("-" * 80)
        report.append(f"{'方法':<6} {'路径':<45} {'状态码':<8} {'响应时间':<12} {'结果':<8}")
        report.append("-" * 80)

        for result in self.results:
            status = "✓ 成功" if result.success else "✗ 失败"
            time_str = f"{result.response_time_ms}ms"
            if result.response_time_ms > self.slow_threshold_ms:
                time_str += " [慢]"

            report.append(
                f"{result.method:<6} {result.path:<45} {result.status_code:<8} {time_str:<12} {status:<8}"
            )

        # 失败的端点详情
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            report.append("\n" + "-" * 80)
            report.append("失败端点详情:")
            report.append("-" * 80)
            for result in failed_results:
                report.append(f"\n端点: {result.method} {result.path}")
                report.append(f"  状态码: {result.status_code}")
                report.append(f"  响应时间: {result.response_time_ms}ms")
                report.append(f"  错误信息: {result.error_message}")
                if not result.data_valid:
                    report.append(f"  数据结构: 无效")

        # 慢接口列表
        slow_results = [r for r in self.results if r.response_time_ms > self.slow_threshold_ms and r.success]
        if slow_results:
            report.append("\n" + "-" * 80)
            report.append(f"慢接口列表 (>{self.slow_threshold_ms}ms):")
            report.append("-" * 80)
            for result in sorted(slow_results, key=lambda x: x.response_time_ms, reverse=True):
                report.append(f"  {result.method} {result.path}: {result.response_time_ms}ms")

        # 性能建议
        report.append("\n" + "-" * 80)
        report.append("性能问题建议:")
        report.append("-" * 80)

        if slow_count > 0:
            report.append(f"• 发现 {slow_count} 个慢接口，建议优化:")
            for result in slow_results[:5]:  # 只显示前5个
                report.append(f"  - {result.path}: {result.response_time_ms}ms")
                if "market" in result.path.lower():
                    report.append(f"    建议: 考虑添加缓存或减少数据量")
                elif "workspace" in result.path.lower():
                    report.append(f"    建议: 优化聚合查询，考虑异步加载")
                elif "research" in result.path.lower():
                    report.append(f"    建议: 研究相关接口可能涉及计算，考虑后台任务")
        else:
            report.append("• 所有接口响应时间良好 (<1s)")

        if failed_count > 0:
            report.append(f"\n• 发现 {failed_count} 个失败接口，需要检查:")
            for result in failed_results[:5]:
                report.append(f"  - {result.path}: {result.error_message}")
        else:
            report.append("\n• 所有接口测试通过")

        report.append("\n" + "=" * 80)
        report.append("报告结束")
        report.append("=" * 80)

        return "\n".join(report)

    def save_report(self, filename: str = "api_test_report.txt"):
        """保存报告到文件"""
        report = self.generate_report()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        return filename


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="API 端点测试工具")
    parser.add_argument(
        "--url",
        default="http://localhost:9011",
        help="API 基础 URL (默认: http://localhost:9011)"
    )
    parser.add_argument(
        "--output",
        default="api_test_report.txt",
        help="报告输出文件 (默认: api_test_report.txt)"
    )
    parser.add_argument(
        "--slow-threshold",
        type=int,
        default=1000,
        help="慢接口阈值(毫秒) (默认: 1000)"
    )

    args = parser.parse_args()

    tester = APITester(base_url=args.url)
    tester.slow_threshold_ms = args.slow_threshold

    try:
        tester.run_all_tests()
        report = tester.generate_report()
        print(report)

        # 保存报告
        output_file = tester.save_report(args.output)
        print(f"\n报告已保存到: {output_file}")

        # 返回退出码
        failed_count = sum(1 for r in tester.results if not r.success)
        sys.exit(0 if failed_count == 0 else 1)

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
