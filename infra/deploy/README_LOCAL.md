# ⚠️ 本地开发禁止启动 Docker 服务

根据 AGENTS.md 规定，**本项目严格禁止在本地环境运行任何Docker服务**。

## 所有服务必须在服务器运行

```
本地WSL (代码编辑) --> Git Push --> 服务器 (ssh djy@39.106.11.65) --> Docker运行
```

## 本地请勿执行

```bash
# ❌ 禁止在本地执行
docker compose up -d
docker compose up

# ✅ 正确做法：在服务器上执行
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
cd ~/Quant/infra/deploy
docker compose up -d
```

## 本地开发方式

1. 修改代码
2. `git add . && git commit -m "xxx" && git push`
3. 在服务器上部署验证
