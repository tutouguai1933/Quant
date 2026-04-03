from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_DOC = REPO_ROOT / "README.md"
ARCH_DOC = REPO_ROOT / "docs" / "architecture.md"
OPS_DOC = REPO_ROOT / "docs" / "ops-freqtrade.md"
DEPLOY_COMPOSE = REPO_ROOT / "infra" / "deploy" / "docker-compose.yml"
DEPLOY_ENV = REPO_ROOT / "infra" / "deploy" / ".env.example"
API_ENV = REPO_ROOT / "infra" / "deploy" / "api.env.example"
API_DOCKERFILE = REPO_ROOT / "services" / "api" / "Dockerfile"
WEB_DOCKERFILE = REPO_ROOT / "apps" / "web" / "Dockerfile"
WEB_API_MODULE = REPO_ROOT / "apps" / "web" / "lib" / "api.ts"
MIHOMO_README = REPO_ROOT / "infra" / "mihomo" / "README.md"
FREQTRADE_PROXY_CONFIG = REPO_ROOT / "infra" / "freqtrade" / "user_data" / "config.proxy.noop.json"
FREQTRADE_DEPLOY_CONFIG = REPO_ROOT / "infra" / "freqtrade" / "user_data" / "config.deploy.json"


class ServerDeploymentDocsTests(unittest.TestCase):
    def test_server_deploy_files_exist(self) -> None:
        self.assertTrue(DEPLOY_COMPOSE.exists(), f"missing file: {DEPLOY_COMPOSE}")
        self.assertTrue(DEPLOY_ENV.exists(), f"missing file: {DEPLOY_ENV}")
        self.assertTrue(API_ENV.exists(), f"missing file: {API_ENV}")
        self.assertTrue(API_DOCKERFILE.exists(), f"missing file: {API_DOCKERFILE}")
        self.assertTrue(WEB_DOCKERFILE.exists(), f"missing file: {WEB_DOCKERFILE}")
        self.assertTrue(MIHOMO_README.exists(), f"missing file: {MIHOMO_README}")
        self.assertTrue(FREQTRADE_PROXY_CONFIG.exists(), f"missing file: {FREQTRADE_PROXY_CONFIG}")
        self.assertTrue(FREQTRADE_DEPLOY_CONFIG.exists(), f"missing file: {FREQTRADE_DEPLOY_CONFIG}")

    def test_server_deploy_compose_uses_quant_ports(self) -> None:
        content = DEPLOY_COMPOSE.read_text(encoding="utf-8")

        self.assertIn("QUANT_API_PORT", content)
        self.assertIn(":9011", content)
        self.assertIn("QUANT_WEB_PORT", content)
        self.assertIn(":9012", content)
        self.assertIn("QUANT_FREQTRADE_PORT", content)
        self.assertIn(":8080", content)
        self.assertIn("quant-api", content)
        self.assertIn("quant-web", content)
        self.assertIn("quant-freqtrade", content)
        self.assertIn("mihomo", content)
        self.assertIn("QUANT_MIHOMO_PORT", content)
        self.assertIn("QUANT_FREQTRADE_DEPLOY_CONFIG", content)

    def test_docs_explain_github_server_baseline_and_debug_ports(self) -> None:
        readme_content = README_DOC.read_text(encoding="utf-8")
        arch_content = ARCH_DOC.read_text(encoding="utf-8")
        ops_content = OPS_DOC.read_text(encoding="utf-8")
        mihomo_content = MIHOMO_README.read_text(encoding="utf-8")

        self.assertIn("GitHub", readme_content)
        self.assertIn("阿里云服务器", readme_content)
        self.assertIn("Quant-Debug-N", readme_content)
        self.assertIn("9011", readme_content)
        self.assertIn("9012", readme_content)
        self.assertIn("data-api.binance.vision", readme_content)
        self.assertIn("GitHub", arch_content)
        self.assertIn("api.binance.com", arch_content)
        self.assertIn("端口", ops_content)
        self.assertIn("Quant-Debug-N", ops_content)
        self.assertIn("9011", ops_content)
        self.assertIn("9012", ops_content)
        self.assertIn("data-api.binance.vision", ops_content)
        self.assertIn("Mihomo", mihomo_content)
        self.assertIn("固定", mihomo_content)

    def test_web_api_module_supports_server_env_base_url(self) -> None:
        content = WEB_API_MODULE.read_text(encoding="utf-8")

        self.assertIn("QUANT_API_BASE_URL", content)
        self.assertIn("process.env", content)

    def test_api_env_example_includes_split_binance_endpoints(self) -> None:
        content = API_ENV.read_text(encoding="utf-8")

        self.assertIn("QUANT_BINANCE_MARKET_BASE_URL", content)
        self.assertIn("QUANT_BINANCE_ACCOUNT_BASE_URL", content)
        self.assertIn("QUANT_BINANCE_TIMEOUT_SECONDS", content)

    def test_deploy_examples_include_proxy_envs(self) -> None:
        deploy_env = DEPLOY_ENV.read_text(encoding="utf-8")
        api_env = API_ENV.read_text(encoding="utf-8")

        self.assertIn("QUANT_MIHOMO_IMAGE", deploy_env)
        self.assertIn("QUANT_MIHOMO_PORT", deploy_env)
        self.assertIn("QUANT_MIHOMO_CONTROLLER_PORT", deploy_env)
        self.assertIn("HTTP_PROXY", api_env)
        self.assertIn("HTTPS_PROXY", api_env)
        self.assertIn("ALL_PROXY", api_env)


if __name__ == "__main__":
    unittest.main()
