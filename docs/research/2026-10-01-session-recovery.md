# 2026-10-01 部署后登录失效修复

## 用户现象与证据
用户看到“自动化状态加载失败：后端数据暂不可用，可能已重新部署，请刷新或重新登录”。
现场API/Web健康，重启计数0、OOM=false；失效令牌请求automation接口得到HTTP200+unauthorized信封。
auth/session也明确返回session_not_found。原AuthService只把登录放内存，API重建丢失旧登录。
前端getAutomationStatus把鉴权错误覆盖为统一后端降级提示；SessionGuard原本只在路由变化时检查，打开的旧页面不会及时回登录。
旧令牌已经失效，无法凭空恢复，需要用户重新登录一次。

## 修复
- QUANT_SESSION_STATE_PATH挂载到/app/.runtime/auth_sessions.json，有效会话跨API重建保存。
- 文件只保存高熵令牌的SHA256摘要、不保存Bearer原文；临时文件0600，fsync后原子替换；密码变更或到期失效，损坏文件显式记录错误并拒绝恢复。
- 登录与登出都有锁保护并同步保存；仅针对现有单uvicorn进程部署，不承诺多个同时运行的API进程共享会话。
- 前端明确区分anonymous/authenticated/expired/unavailable；只有确认过期才跳登录，短时断网或503保留令牌与当前页面。
- HTTP401和HTTP200鉴权错误信封都通知会话守卫；聚焦、页面恢复可见、每60秒也复核会话。
- 自动化错误保留“登录已失效，请重新登录”，不再误报后端不可达。
- Web在服务器现有Next15.5.24依赖镜像中编译，构建过程不安装/恢复/升级依赖；768MB RAM/1536MB RAM+swap、Node堆384MB、单构建worker。
- 构建期间暂停API/Web并配置失败自动恢复，发布命令不重启交易容器。另排除合计约414MB的旧Next构建备份。

## 验证
- 鉴权测试12通过、0失败；前端会话状态检查5通过、0失败；TypeScript检查和生产构建通过。
- 真实浏览器10通过、0失败，覆盖页面数据、失效会话重新登录、短时不可达保持页面。
- 明确启用的实际API重启验证1通过、0失败：同一cookie在API重启后仍已认证，automation接口仍正常。
- 独立审查发现的断网误判已补回归并复审通过。
- 可复现重启验证脚本为docs/research/2026-10-01-session-restart-verification.cjs，默认必须显式启用；不可把它作为普通UI测试自动运行。

## 回滚
原deploy-api、deploy-web与quant-api-runtime:before-session镜像保留。
可只恢复API/Web镜像；不要删除运行卷或auth_sessions.json，也不要更改交易策略/账户配置。
回滚到纯内存会话的旧API会要求重新登录。
