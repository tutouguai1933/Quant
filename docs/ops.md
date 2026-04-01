# Quant Ops

## 当前运行结论

仓库现在已经可以真实启动，不再是“只能看文档和骨架”的状态。

当前已经验证过：

- API 可以启动
- WebUI 可以启动
- Binance 真实行情可以读取
- Binance 真实余额可以读取
- `dry-run` 链路可以跑通

## 当前运行方式

默认约定：

- 所有 Python 相关命令默认在 conda 环境 `quant` 中执行
- 如果没有特别说明，后端服务、测试和脚本都先进入这个环境再运行

### API

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
set -a
source /home/djy/Quant/.env.quant.local
set +a
uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

### WebUI

```bash
cd apps/web
pnpm start --hostname 127.0.0.1 --port 3000
```

### 默认地址

- API：`http://127.0.0.1:8000`
- WebUI：`http://127.0.0.1:3000`

## 当前账号

- 用户名：`admin`
- 密码：`1933`

## 当前模式

### `demo`

- 纯演示模式

### `dry-run`

- 读取真实 Binance 数据
- 执行仍走 dry-run
- 当前推荐一直用这个模式联调

### `live`

- 当前仍然故意拦住
- 还不能真实下单

## 真实 dry-run 已验证链路

已经验证通过的链路：

1. 登录控制台
2. 运行信号流水线
3. 启动策略
4. 派发最新信号
5. 查看订单
6. 查看持仓
7. 查看风险或任务反馈

## 最小演示流程

固定入口：

- `infra/scripts/demo_flow.ps1`

固定步骤：

1. 创建或导入一个策略定义
2. 生成一批 mock 或策略信号
3. 执行基础风控判断
4. 将可执行信号交给执行器
5. 同步订单、持仓、余额、策略状态
6. 在 WebUI 中看到结果
7. 人为制造一个失败任务或风险事件并确认可见

固定异常检查：

- 风控拒绝
- 失败任务

## 一条龙体验路径

前提：

- Python 相关命令默认使用 conda 环境 `quant`

### 页面体验

1. 打开 `http://127.0.0.1:3000/login`
2. 用 `admin / 1933` 登录
3. 打开 `http://127.0.0.1:3000/market`
4. 打开任一单币图表页
5. 打开 `http://127.0.0.1:3000/strategies`
6. 先点“启动策略”
7. 再点“派发最新信号”
8. 查看 `orders`、`positions`、`tasks`、`risk`

### 脚本体验

```powershell
pwsh -File infra/scripts/demo_flow.ps1 -Username admin -Password 1933
```

## 当前需要你准备的东西

如果只是继续 `dry-run`，你需要：

- Binance API Key
- Binance API Secret
- `.env.quant.local`

如果只是看演示壳，不需要真实密钥。  
如果要读真实行情和真实余额，就需要 Binance 密钥。

## 当前运维边界

- 只支持 `crypto`
- 只支持 `Binance`
- 只支持 `Freqtrade`
- 当前主模式是 `dry-run`
- 真实下单未开放

## 当前文档关系

- [README.md](/home/djy/Quant/README.md)：项目现状
- [plan.md](/home/djy/Quant/plan.md)：当前推进顺序
- [architecture.md](/home/djy/Quant/docs/architecture.md)：模块职责
- [api.md](/home/djy/Quant/docs/api.md)：接口边界
