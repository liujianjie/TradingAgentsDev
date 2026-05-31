# LLM API Key 配置（已迁移）

> 此文档已被替代。请改看 [setup-apikeys.md](./setup-apikeys.md)

新方案不再用环境变量，而是用 `config/apikeys.local.json` 集中管理所有密钥（LLM + Server酱），Python 和 C# 都从它读。
