# 首页显示账户总余额

**Goal:** 首页首屏显示已核对的现货与合约总权益，点击可跳余额明细，读取失败不能假装余额为零。
**Architecture:** 复用已部署的/balances/summary；新增独立余额卡，不与首页慢接口互相等待。仅登录后读取，单飞刷新、隐藏页面暂停轮询、卸载取消请求；现货/合约分开展示。首页Suspense入口保留初始HTML节点。
**Tech Stack:** Next.js/React/TypeScript/Playwright，既有后端不变。

- [x] 先用真实线上页面复现首屏缺少账户余额。
- [x] 实现独立首页余额卡，保留原三张核心状态卡。
- [x] 验证HTML、脚本、真实金额和明细跳转、失败后刷新恢复；类型检查。
- [x] 独立分支提交推送，服务器仅构建Web，保留API/交易实例与原有修改。
- [x] 更新CONTEXT和部署记录。策略优化只整理假设和验证顺序，不调参、训练或试单。

Windows验证：
```powershell
wsl -d Ubuntu-22.04 -- bash /home/djy/Quant/docs/research/2026-10-04-check-home-account-equity.sh
```
预期真实页面测试全部通过，不启动本地Docker或安装依赖。
