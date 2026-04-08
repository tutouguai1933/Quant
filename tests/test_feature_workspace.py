from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"
CONFIG_SERVICE = REPO_ROOT / "services" / "api" / "app" / "services" / "workbench_config_service.py"


class FeatureWorkspaceTests(unittest.TestCase):
    def test_feature_workspace_page_exists(self) -> None:
        self.assertTrue((WEB_APP / "features" / "page.tsx").exists())

    def test_navigation_contains_feature_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/features"', shell_content)

    def test_feature_workspace_page_mentions_factor_sections(self) -> None:
        content = (WEB_APP / "features" / "page.tsx").read_text(encoding="utf-8")
        config_content = CONFIG_SERVICE.read_text(encoding="utf-8")
        self.assertIn("特征工作台", content)
        self.assertIn("因子分组", content)
        self.assertIn("主判断因子", content)
        self.assertIn("辅助确认因子", content)
        self.assertIn("预处理规则", content)
        self.assertIn("missing_policy", content)
        self.assertIn("outlier_policy", content)
        self.assertIn("normalization_policy", content)
        self.assertIn("特征版本", content)
        self.assertIn("因子组合配置", content)
        self.assertIn("因子预设", content)
        self.assertIn("balanced_default", content)
        self.assertIn("trend_focus", config_content)
        self.assertIn("confirmation_focus", config_content)
        self.assertIn("primary_factors", content)
        self.assertIn("当前配置", content)
        self.assertIn("研究页权重入口", content)
        self.assertIn("研究页权重入口", content)
        self.assertIn("主要影响什么", content)
        self.assertIn("工作台暂时不可用", content)
        self.assertIn("WorkbenchConfigStatusCard", content)


if __name__ == "__main__":
    unittest.main()
