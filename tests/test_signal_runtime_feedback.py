from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNALS_PAGE = REPO_ROOT / "apps" / "web" / "app" / "signals" / "page.tsx"
API_FILE = REPO_ROOT / "apps" / "web" / "lib" / "api.ts"
RUNTIME_COMPONENT = REPO_ROOT / "apps" / "web" / "components" / "research-runtime-panel.tsx"


class SignalRuntimeFeedbackTests(unittest.TestCase):
    def test_signals_page_mentions_runtime_feedback(self) -> None:
        content = SIGNALS_PAGE.read_text(encoding="utf-8")
        runtime_content = RUNTIME_COMPONENT.read_text(encoding="utf-8")
        self.assertIn("ResearchRuntimePanel", content)
        self.assertIn("研究运行状态", runtime_content)
        self.assertIn("预计时长", runtime_content)
        self.assertIn("完成后去哪里看", runtime_content)

    def test_api_client_exposes_research_runtime_status(self) -> None:
        content = API_FILE.read_text(encoding="utf-8")
        self.assertIn("export type ResearchRuntimeStatusModel", content)
        self.assertIn("getResearchRuntimeStatus", content)
        self.assertIn('"/signals/research/runtime"', content)


if __name__ == "__main__":
    unittest.main()
