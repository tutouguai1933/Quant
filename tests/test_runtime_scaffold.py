from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RuntimeScaffoldTests(unittest.TestCase):
    def test_api_requirements_file_exists(self) -> None:
        requirements = REPO_ROOT / "services" / "api" / "requirements.txt"
        self.assertTrue(requirements.exists(), f"missing file: {requirements}")
        content = requirements.read_text(encoding="utf-8")
        self.assertIn("fastapi", content)
        self.assertIn("uvicorn", content)

    def test_web_package_manifest_exists(self) -> None:
        package_json = REPO_ROOT / "apps" / "web" / "package.json"
        self.assertTrue(package_json.exists(), f"missing file: {package_json}")
        package = json.loads(package_json.read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "quant-web")
        self.assertIn("dev", package["scripts"])
        self.assertIn("build", package["scripts"])
        self.assertIn("next", package["dependencies"])

    def test_web_app_runtime_files_exist(self) -> None:
        expected_files = [
            REPO_ROOT / "apps" / "web" / "app" / "layout.tsx",
            REPO_ROOT / "apps" / "web" / "app" / "globals.css",
            REPO_ROOT / "apps" / "web" / "tsconfig.json",
            REPO_ROOT / "apps" / "web" / "next-env.d.ts",
        ]
        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_freqtrade_compose_binds_rest_api_to_localhost_only(self) -> None:
        compose_file = REPO_ROOT / "infra" / "freqtrade" / "docker-compose.yml"
        self.assertTrue(compose_file.exists(), f"missing file: {compose_file}")
        compose_content = compose_file.read_text(encoding="utf-8")
        self.assertIn("network_mode: host", compose_content)

        base_config = REPO_ROOT / "infra" / "freqtrade" / "user_data" / "config.base.json"
        self.assertTrue(base_config.exists(), f"missing file: {base_config}")
        base_content = base_config.read_text(encoding="utf-8")
        self.assertIn('"listen_ip_address": "127.0.0.1"', base_content)


if __name__ == "__main__":
    unittest.main()
