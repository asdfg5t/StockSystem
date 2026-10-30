# Research reproducibility / 研究复现

This project provides experiment tools without an independently verified accuracy guarantee. Pin the commit and entry point: scripts can differ in training strategy and artifact format.

本仓库提供实验实现，不承诺统一准确率。不同训练入口的处理方式和产物格式可能不同，应固定代码版本与入口。

## Record each experiment / 实验记录

- Git commit, Python/dependency versions, OS, CPU/GPU and CUDA.
- Data provider, download date, stock universe, date range, missing data and adjustment policy.
- Chronological train/validation/test boundaries, features and selection method.
- Lookback, horizon, architecture, optimizer, schedule, batch size, epochs and stopping rule.
- Python/NumPy/PyTorch seeds and deterministic settings. There is no single global seed enforced across all scripts.
- Held-out metrics, simple baseline, artifacts and exact command.

记录数据范围、复权口径、划分日期、特征、模型参数、种子、环境与基线。项目尚未对所有训练入口统一设置随机种子，跨硬件结果可能不同。

## Evaluation / 评估

Use chronological splits and fit preprocessing only on training data. Check horizon overlap at boundaries, feature selection scope and future-dependent features for your chosen script. Do not tune on the test set. Compare models on matching splits; report price errors and direction metrics separately.

按时间划分，标准化、降维与特征选择应仅使用训练集。检查多步标签跨边界重叠及未来信息，避免测试集调参。相同划分下对比模型；价格拟合度本身不能证明交易盈利。

Backtests require explicit costs, slippage, execution timing and tradability assumptions. Inspect existing simulations before making performance claims. 回测需明确成本、滑点、执行时间和可交易性；现有页面不等同于经过实盘验证的交易系统。

## Artifacts / 产物

Keep weights with matching scalers, PCA/selected features and database model records. Check paths when moving environments. Only load trusted `.pth`, pickle and joblib files. Raw data and generated artifacts are ignored by Git; obtain data under provider terms and train locally. No pretrained release is bundled.

模型文件须成套保存，迁移环境应检查路径，仅加载可信文件。仓库不包含本地实验结果或预训练发布包。
