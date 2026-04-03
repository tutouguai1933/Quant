# Quant 第一阶段最小演示脚本。
# 这个脚本用于串起登录、生成信号、风控放行、执行、同步，以及失败场景验证。
# 固定示例路径：
# - /api/v1/auth/login
# - /api/v1/signals/pipeline/run
# - /api/v1/strategies/1/start
# - /api/v1/strategies/1/dispatch-latest-signal
# - /api/v1/risk-events
# - /api/v1/tasks/reconcile

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:9011",
    [string]$WebUiBaseUrl = "http://127.0.0.1:9012",
    [string]$Username = "admin",
    [string]$Password = "1933",
    [int]$StrategyId = 1,
    [string]$PipelineSource = "mock"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param(
        [string]$Number,
        [string]$Title
    )

    Write-Host ""
    Write-Host "[$Number] $Title" -ForegroundColor Cyan
}

function Invoke-QuantApi {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [string]$Token = ""
    )

    $headers = @{
        Accept = "application/json"
    }

    if ($Token) {
        $headers["Authorization"] = "Bearer $Token"
    }

    $request = @{
        Method      = $Method
        Uri         = "$ApiBaseUrl$Path"
        Headers     = $headers
        ErrorAction = "Stop"
    }

    if ($null -ne $Body) {
        $request["Body"] = ($Body | ConvertTo-Json -Depth 6)
        $request["ContentType"] = "application/json"
    }

    return Invoke-RestMethod @request
}

function Assert-NoApiError {
    param(
        [object]$Response,
        [string]$StepName
    )

    if ($null -ne $Response.error) {
        throw "$StepName 失败: $($Response.error.code) - $($Response.error.message)"
    }
}

Write-Host "Quant 最小演示开始" -ForegroundColor Green
Write-Host "API: $ApiBaseUrl"
Write-Host "WebUI: $WebUiBaseUrl"

Write-Step "1" "登录控制平面并获取会话令牌"
$login = Invoke-QuantApi -Method "POST" -Path "/api/v1/auth/login" -Body @{
    username = $Username
    password = $Password
}
Assert-NoApiError -Response $login -StepName "登录"
$token = [string]$login.data.item.token
Write-Host "已获取管理员令牌。"

Write-Step "2" "创建或启用演示策略"
$startStrategy = Invoke-QuantApi -Method "POST" -Path "/api/v1/strategies/$StrategyId/start" -Token $token
Assert-NoApiError -Response $startStrategy -StepName "启动策略"
Write-Host "策略状态: $($startStrategy.data.item.status)"

Write-Step "3" "生成 mock 信号"
$train = Invoke-QuantApi -Method "POST" -Path "/api/v1/signals/pipeline/run?source=$PipelineSource"
Assert-NoApiError -Response $train -StepName "生成信号"
Write-Host "本次输出信号数: $($train.data.run.signal_count)"

Write-Step "4" "执行风控、派发信号并同步执行结果"
$dispatch = Invoke-QuantApi -Method "POST" -Path "/api/v1/strategies/$StrategyId/dispatch-latest-signal" -Token $token
Assert-NoApiError -Response $dispatch -StepName "派发最新信号"
Write-Host "风控结果: $($dispatch.data.risk_decision.status)"
Write-Host "订单编号: $($dispatch.data.item.order.id)"
Write-Host "同步任务状态: $($dispatch.data.sync_task.status)"

Write-Step "5" "检查订单、持仓和策略状态"
$orders = Invoke-QuantApi -Method "GET" -Path "/api/v1/orders"
Assert-NoApiError -Response $orders -StepName "查询订单"
$positions = Invoke-QuantApi -Method "GET" -Path "/api/v1/positions"
Assert-NoApiError -Response $positions -StepName "查询持仓"
$strategies = Invoke-QuantApi -Method "GET" -Path "/api/v1/strategies" -Token $token
Assert-NoApiError -Response $strategies -StepName "查询策略"
Write-Host "订单数量: $($orders.data.items.Count)"
Write-Host "持仓数量: $($positions.data.items.Count)"
Write-Host "策略数量: $($strategies.data.items.Count)"

Write-Step "6" "到 WebUI 页面查看结果"
Write-Host "建议检查这些页面："
Write-Host "$WebUiBaseUrl/signals"
Write-Host "$WebUiBaseUrl/strategies"
Write-Host "$WebUiBaseUrl/orders"
Write-Host "$WebUiBaseUrl/positions"
Write-Host "$WebUiBaseUrl/risk"
Write-Host "$WebUiBaseUrl/tasks"

Write-Step "7A" "制造风控拒绝并确认风险事件可见"
$stopStrategy = Invoke-QuantApi -Method "POST" -Path "/api/v1/strategies/$StrategyId/stop" -Token $token
Assert-NoApiError -Response $stopStrategy -StepName "停止策略"
$blockedDispatch = Invoke-QuantApi -Method "POST" -Path "/api/v1/strategies/$StrategyId/dispatch-latest-signal" -Token $token
if ($null -eq $blockedDispatch.error -or $blockedDispatch.error.code -ne "risk_blocked") {
    throw "风控拒绝场景未出现预期结果。"
}
$riskEvents = Invoke-QuantApi -Method "GET" -Path "/api/v1/risk-events" -Token $token
Assert-NoApiError -Response $riskEvents -StepName "查询风险事件"
Write-Host "最近风险事件数: $($riskEvents.data.items.Count)"

Write-Step "7B" "制造失败任务并确认异常可见"
$failedTask = Invoke-QuantApi -Method "POST" -Path "/api/v1/tasks/reconcile?simulate_failure=true" -Token $token
Assert-NoApiError -Response $failedTask -StepName "制造失败任务"
if ($failedTask.data.item.status -ne "failed") {
    throw "失败任务场景未出现预期结果。"
}
$tasks = Invoke-QuantApi -Method "GET" -Path "/api/v1/tasks" -Token $token
Assert-NoApiError -Response $tasks -StepName "查询任务列表"
Write-Host "最新失败任务状态: $($failedTask.data.item.status)"
Write-Host "任务列表数量: $($tasks.data.items.Count)"

Write-Host ""
Write-Host "演示完成。若需要恢复策略，可重新调用 /api/v1/strategies/$StrategyId/start。" -ForegroundColor Green
