# 2026-10-01 网站断链与内存审查

## 范围
梳理前端、API、研究训练、交易策略、代理、巡检和监控的模块关系；重点逐段审查故障相关代码与部署配置。
仓库核心目录共563个已跟踪文件，未声称逐行审查每个文件。排除依赖目录、运行数据、私钥与数据库内容。
开发入口改用Windows Codex/PowerShell，项目、Conda quant环境和现有Linux工具仍由WSL承载，不迁移依赖。

## 现场证据
- 服务器内存1612MB，交换空间3072MB；首次检查swap已用2413MB，可用内存378MB。
- Web仍为healthy且服务器本机返回200；API显示Exited(137)，9011端口accept队列2049/2048，health超时。
- 内核日志明确记录2026-08-31与2026-09-07杀死uvicorn，两个Freqtrade实例也出现过全机OOM。
- Docker记录存在stale containerd task错误，RestartPolicy=unless-stopped仍未恢复。
- 旧uvicorn进程1891938仍在API容器cgroup，等待pipe_write，VmHWM792900KB、VmSwap977344KB。因此退出码137之外还有进程/容器状态不同步和日志输出堵塞。
- API/Web没有内存或swap边界；API同步线程上限200；API与OpenClaw同时启动定时巡检。
- KlineStore初始化解析64个历史文件并保留全部bar字典；增量同步last_timestamp也会暖入全量读取缓存。
- logging仅文件写入入队，控制台仍同步输出；原文件日志队列无容量上限。
- 本地与服务器均有上一轮未提交修复；服务器master还领先远端两次运行配置提交，不能直接覆盖或reset。

## 已实施修复
- K线索引逐行构建；时间戳只保留轻量结果；全局读取缓存最多5000行，LRU淘汰。
- 大历史仍完整返回；同文件同版本的并发读取通过临时Future共享；不同文件解析串行降低瞬时峰值，失败唤醒等待者。
- 文件和控制台都使用后台日志消费；积压最多1000条，超出时计数丢弃；Docker日志也设置non-blocking和1MB缓冲。
- API资源边界640MB RAM / 896MB RAM+swap；Web384MB / 512MB，Node堆256MB。所有值可通过配置覆盖。
- API同步路由上限200改为默认40，可配置；数值计算默认单线程、限制glibc分配arena。
- 默认关闭API重复巡检，保留OpenClaw调度。
- 写配置后立即更新缓存并失效控制参数缓存；复盘报告缓存按条数和任务版本失效，修复新增任务/已完成任务不显示的问题。
- 复用服务器现有依赖镜像，仅COPY代码，不安装、恢复或升级依赖；仅重新创建API/Web。

## 全项目审查中尚未实施的空间
| 优先级 | 证据与影响 | 边界 |
|---|---|---|
| P1 | ResearchService直接在API进程执行训练、推理和walk-forward，超时只停止等待，线程仍继续执行 | 重任务隔离到独立受限worker是后续架构工作，本次不改执行语义 |
| P1 | 两个Freqtrade实例初查约583MB常驻，叠加API与系统本身，小内存仍紧张 | 本次不重启或限制交易进程；长期需要整体容量规划 |
| P1 | 自愈逻辑依赖API自身；OpenClaw在API失联时只能继续请求失败 | 本次修复日志反压和重建状态；独立主机看门狗尚未加入 |
| P1 | performance中间件以原始URL建长期字典，公网扫描会增加端点数量 | 后续应按路由模板聚合并限制端点基数 |
| P1 | /openclaw/patrol无令牌也允许执行，并未验证请求来自内部；生产API监听公网 | 本次未改变接口访问控制，需独立验证后收紧网络与鉴权 |
| P2 | Freqtrade stable镜像与部分依赖使用浮动版本，历史已有代理字段不兼容 | 本次不改依赖或镜像版本 |
| P2 | Docker构建层包含依赖安装，Web构建堆上限1024MB，曾与API负载共同耗尽内存 | 本次使用代码层发布，完整构建仍需资源守卫 |
| P2 | scripts/deploy.sh、verify.sh部分检查仍使用旧端口3000/3001；部分文档默认值滞后 | 新增Windows与代码层发布说明；不执行旧脚本 |

## 验证与回滚
先补回归测试复现失败，再修复；默认值测试按原HEAD的16币、15m及量能阈值修正，不修改交易币种或参数。
- 后端157通过、0失败；独立审查发现的大历史并发缺口已修复并复审通过。
- Playwright主链路/脚本/资源检查7通过、0失败；额外登录、点击任务页、接口数据与页面状态检查1通过、0失败。
- 2026-10-01 03:11（香港时间）API/Web均running+healthy，重启0次，OOM=false；Web200约9ms，health200约3ms。
- 页面检查期间API约403MiB；最终空闲采样API132MiB、Web98MiB。全机可用内存545MB，swap使用1323MB（初查2413MB）。
- API/Web资源上限、非阻塞日志、40线程、5000行缓存和唯一巡检配置均已在实际容器检查。
- 服务容器内通常为UTC，报告按用户香港时区标注。
- 这是短期恢复与交互验证，未做强制训练或多轮性能实验，不承诺长期峰值负载不会触发资源限制。
- 新分支仅提交本次差异；部署在服务器现有已修复工作树上，原本未提交的修复继续保留。
- 首次代码层构建仍发送476.7MB上下文；随后补充.dockerignore排除运行资料、历史hyperopt与合约私钥，后续构建不再携带这些目录。
- 本地证据截图保留在docs/research/2026-10-01-tasks-restored.png，不推送账户页面截图。
原deploy-api与deploy-web镜像保留；代码回退仅涉及本次补丁；不删除数据卷、不触碰交易数据库。

## 参考
- [Docker内存与swap语义](https://docs.docker.com/engine/containers/resource_constraints/)
- [Compose服务资源与日志配置](https://docs.docker.com/reference/compose-file/services/)
- [Starlette同步线程池](https://www.starlette.io/threadpool/)

## 后续用户反馈闭环
用户的自动化状态提示已定位到部署丢失内存登录，并非再次OOM。
会话持久化、错误语义与失效登录自动返回入口已部署并通过真实API重启验证；详见2026-10-01-session-recovery.md。
构建上下文还发现约414MB旧Next备份，已补充忽略规则；没有删除服务器历史文件。
