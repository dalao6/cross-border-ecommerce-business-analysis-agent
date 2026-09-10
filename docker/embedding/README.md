# Embedding 模型说明

这里存放 Embedding 服务使用的模型文件：**BAAI/bge-large-zh-v1.5**（约 1.1GB，向量维度 1024）。

## 模型来源

模型已在 `../shopkeeper-agent/docker/embedding/bge-large-zh-v1.5` 下载完成。

## 放置方式（二选一）

1. **复用已有模型（默认）**：`docker-compose.yaml` 中 embedding 服务的挂载源已指向
   `../shopkeeper-agent/docker/embedding/bge-large-zh-v1.5`，无需额外操作。

2. **独立部署**：把模型复制到本目录：
   ```bash
   cp -r ../shopkeeper-agent/docker/embedding/bge-large-zh-v1.5 ./bge-large-zh-v1.5
   ```
   然后把 `docker-compose.yaml` 里 embedding 的挂载源改为 `./embedding/bge-large-zh-v1.5`。

## 模型文件清单

- `pytorch_model.bin`（模型权重，约 1.3GB）
- `config.json` / `config_sentence_transformers.json` / `sentence_bert_config.json`
- `modules.json` / `1_Pooling/config.json`
- `tokenizer.json` / `tokenizer_config.json` / `special_tokens_map.json` / `vocab.txt`
