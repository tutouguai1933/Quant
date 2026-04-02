from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class FreqtradeDeploymentDocsTests(unittest.TestCase):
    def test_freqtrade_docker_files_exist(self) -> None:
        self.assertTrue((REPO_ROOT / "infra/freqtrade/docker-compose.yml").exists())
        self.assertTrue((REPO_ROOT / "infra/freqtrade/.env.example").exists())
        self.assertTrue((REPO_ROOT / "infra/freqtrade/user_data/config.base.json").exists())
        self.assertTrue((REPO_ROOT / "infra/freqtrade/user_data/config.private.json.example").exists())
        self.assertTrue((REPO_ROOT / "infra/freqtrade/user_data/strategies/SampleStrategy.py").exists())

    def test_freqtrade_readme_mentions_spot_dry_run_and_symbols(self) -> None:
        content = (REPO_ROOT / "infra/freqtrade/README.md").read_text(encoding="utf-8")

        self.assertIn("Spot", content)
        self.assertIn("dry-run", content)
        self.assertIn("Docker", content)
        self.assertIn("BTC/USDT", content)
        self.assertIn("ETH/USDT", content)
        self.assertIn("SOL/USDT", content)
        self.assertIn("DOGE/USDT", content)

    def test_base_config_is_spot_and_has_rest_api(self) -> None:
        content = (REPO_ROOT / "infra/freqtrade/user_data/config.base.json").read_text(encoding="utf-8")

        self.assertIn('"trading_mode": "spot"', content)
        self.assertIn('"dry_run": true', content)
        self.assertIn('"listen_port": 8080', content)
        self.assertIn('"entry_pricing"', content)
        self.assertIn('"exit_pricing"', content)
        self.assertIn('"enable_ws": false', content)
        self.assertIn('"force_entry_enable": true', content)
        self.assertIn('"BTC/USDT"', content)
        self.assertIn('"DOGE/USDT"', content)


if __name__ == "__main__":
    unittest.main()
