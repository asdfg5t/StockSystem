# Contributing / 贡献指南

感谢参与 StockAI。提交前请先阅读 [中文说明](README.md) 或 [English guide](README.en.md)。

1. 为缺陷或功能建立 Issue，说明复现步骤、预期行为及运行环境。
2. 从 `main` 创建分支，每次提交聚焦一个问题；同步更新受影响的中英文说明。
3. 提交前运行以下检查。修改训练逻辑时，还应记录数据范围、划分方式、随机种子与实验参数。
4. 通过 Pull Request 说明改动、验证结果及已知限制。

```sh
python -m compileall -q backend
python -m unittest discover -s backend/tests -v
cd frontend
npm ci
npm run build
```

不要提交 `.env`、访问令牌、数据库导出、日志、个人论文、行情原始数据或模型权重。只使用有权分享的图片和数据。不要在 Issue 中公开安全漏洞或凭据，参见 [SECURITY.md](SECURITY.md)。

Please open an issue with reproduction steps, expected behavior and environment details. Create a focused branch from `main`, update both READMEs when needed, run the checks above, and describe validation in your pull request. For training changes, record the dataset period, splits, seed and hyperparameters. Keep credentials, database dumps, private documents, market data and generated weights out of commits.
