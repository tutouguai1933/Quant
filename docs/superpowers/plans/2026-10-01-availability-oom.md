# 网站恢复与 OOM 修复执行记录

**目标**：恢复 9012 网站的数据链路，降低 API 常驻与峰值内存，保留现有交易实例和本地未提交工作。
**范围**：KlineStore、日志处理、API 并发、API/Web 部署资源；不改策略参数、账户、数据库或依赖。
**实施依据**：见 docs/research/2026-10-01-availability-audit.md。未启用 /spec、/plan、/do 门控。

1. 收集容器状态、内核 OOM、进程内存及调用链证据；仅尝试 API 重启。
2. 先运行新增回归测试确认失败；实现流式索引、有限 LRU 缓存和非阻塞有界日志。
3. 设置 API 640MB 内存 / 896MB 内存加交换空间、Web 384MB / 512MB、同步并发 40；巡检只由 OpenClaw 调度。
4. 在 Conda quant 环境运行相关测试，检查 Git 差异；只提交本次修改。
5. 推送独立分支；服务器通过 Git 补丁保留现有未提交修复；复用已安装依赖的镜像，不安装或更新依赖。
6. 服务器验证 Compose 配置后只重新创建 API/Web；核验资源边界、线上 HTTP、真实登录和页面切换。
7. 更新 CONTEXT.md、README.md 和排查记录。

验证（PowerShell 调用 WSL，不在本地运行 Docker）：

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'cd /home/djy/Quant; source /home/djy/miniforge3/etc/profile.d/conda.sh; conda activate quant; python -m unittest services.api.tests.test_kline_store_memory services.api.tests.test_kline_store services.api.tests.test_kline_sync_service services.api.tests.test_logging_backpressure -q'
```

预期：37 个测试通过；缓存不会截断历史数据，慢控制台日志不会阻塞调用方。

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'cd /home/djy/Quant/apps/web; QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011 pnpm exec playwright test tests/ui-main-smoke.spec.cjs tests/ui-network.spec.cjs tests/ui-console.spec.cjs --reporter=line'
```

预期：7 个浏览器测试通过；登录、页面切换、脚本与资源加载正常。
回滚：保留原 deploy-api 镜像；恢复部署配置并只重建 API/Web 容器；不删除数据卷。

实际执行结果：后端157通过/0失败；浏览器7通过/0失败；额外交互与数据验证1通过/0失败。
独立审查与复审通过；服务已于2026-10-01部署。配置缓存同步和复盘缓存版本检查是验证中发现的关联修复。
.dockerignore补充排除历史实验和运行文件，减少后续构建上下文。
