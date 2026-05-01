# 飞书告警配置指南

## 当前状态

Grafana告警规则已加载（5条），但飞书Webhook URL使用placeholder，需要配置真实URL才能推送告警。

## 获取飞书机器人Webhook URL

### 方法1：创建自定义机器人（推荐）

1. 打开飞书群聊
2. 点击群设置 → 群机器人 → 添加机器人
3. 选择"自定义机器人"
4. 设置机器人名称（如"Quant告警机器人"）
5. 复制生成的Webhook URL

### 方法2：使用现有OpenClaw飞书应用

已有飞书应用配置：
- App ID: `cli_a9203146ceb89cba`
- App Secret: `PQ4eRzsDq88AY6oFs2oUGgpA5AzpJHbO`

可使用飞书开放平台API发送消息，无需Webhook。

## 配置步骤

### 更新api.env

```bash
# 在服务器上编辑
vim /home/djy/Quant/infra/deploy/api.env

# 添加或更新以下配置
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxx
FEISHU_PUSH_ENABLED=true
```

### 更新Grafana Contact Point

```bash
# 通过API更新
curl -X PUT -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "feishu_webhook",
    "type": "webhook",
    "settings": {
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxx",
      "httpMethod": "POST"
    }
  }' \
  http://127.0.0.1:3000/api/v1/provisioning/contact-points/feishu_webhook
```

### 重启服务

```bash
docker restart quant-api quant-grafana
```

## 告警消息格式

飞书Webhook消息格式（JSON）：
```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": { "tag": "plain_text", "content": "Quant Trading Alert" },
      "template": "red"
    },
    "elements": [
      { "tag": "div", "text": { "tag": "lark_md", "content": "**告警内容**" } }
    ]
  }
}
```

## 验证配置

```bash
# 测试飞书推送
curl -s -X POST http://127.0.0.1:9011/api/v1/feishu/test

# 检查Grafana告警
curl -u admin:admin123 http://127.0.0.1:3000/api/v1/provisioning/alert-rules
```