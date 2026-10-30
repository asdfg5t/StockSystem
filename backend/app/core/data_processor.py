import os
import gc
import json
import shutil
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA, IncrementalPCA
import joblib
from app.config import MODEL_DIR
from app.utils.logger import get_logger

logger = get_logger("data_processor")


class TimeSeriesProcessor:
    """
    时间序列数据处理器 v3
    支持单股票和多股票通用模型两种模式
    """

    def __init__(
        self,
        lookback: int = 30,
        predict_steps: int = 1,
        target_col: str = "close",
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        pca_components: int = 25,
    ):
        self.lookback = lookback
        self.predict_steps = predict_steps
        self.target_col = target_col
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.pca_components = pca_components
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.pca = None
        self.feature_columns: List[str] = []
        self.test_base_prices: np.ndarray = None
        self.stock_id_map: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Single-stock mode (backward compatible)
    # ------------------------------------------------------------------
    def prepare_data(
        self, df: pd.DataFrame, exclude_cols: list = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if exclude_cols is None:
            exclude_cols = ["trade_date"]

        feature_df = df.drop(columns=[c for c in exclude_cols if c in df.columns])
        self.feature_columns = feature_df.columns.tolist()
        close_idx = self.feature_columns.index(self.target_col)

        all_features = feature_df.values.astype(np.float32)
        close_prices = all_features[:, close_idx].copy()

        n = len(all_features)
        test_size = int(n * self.test_ratio)
        val_size = int(n * self.val_ratio)
        train_size = n - val_size - test_size

        min_required = self.lookback + self.predict_steps + 10
        if train_size < min_required:
            raise ValueError(f"训练数据不足: {train_size}条, 至少需要{min_required}条")

        self.feature_scaler.fit(all_features[:train_size])
        scaled_feat = self.feature_scaler.transform(all_features)

        n_comp = min(self.pca_components, scaled_feat.shape[1])
        self.pca = PCA(n_components=n_comp)
        self.pca.fit(scaled_feat[:train_size])
        pca_feat = self.pca.transform(scaled_feat).astype(np.float32)

        explained = sum(self.pca.explained_variance_ratio_) * 100
        logger.info(f"PCA: {scaled_feat.shape[1]}维 → {n_comp}维, 保留方差 {explained:.1f}%")

        X_all, y_all, bp_all = self._create_return_sequences(pca_feat, close_prices)
        if len(X_all) == 0:
            raise ValueError("数据量不足以创建训练序列")

        train_end = max(1, train_size - self.lookback - self.predict_steps + 1)
        val_end = max(train_end + 1, train_size + val_size - self.lookback - self.predict_steps + 1)

        train_X, train_y = X_all[:train_end], y_all[:train_end]
        val_X, val_y = X_all[train_end:val_end], y_all[train_end:val_end]
        test_X, test_y = X_all[val_end:], y_all[val_end:]
        self.test_base_prices = bp_all[val_end:]

        self.target_scaler.fit(train_y)
        train_y = self.target_scaler.transform(train_y).astype(np.float32)
        val_y = self.target_scaler.transform(val_y).astype(np.float32)
        test_y = self.target_scaler.transform(test_y).astype(np.float32)

        logger.info(
            f"数据准备完成: PCA={n_comp}维, "
            f"训练={len(train_X)}, 验证={len(val_X)}, 测试={len(test_X)}"
        )
        return train_X, train_y, val_X, val_y, test_X, test_y

    # ------------------------------------------------------------------
    # Multi-stock universal mode
    # ------------------------------------------------------------------
    def prepare_multi_stock_data(
        self, stock_dfs: Dict[str, pd.DataFrame], exclude_cols: list = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare combined dataset from multiple stocks.
        Each stock is independently split by time, then merged.
        Returns (train_X, train_y, val_X, val_y, test_X, test_y)
        where X has shape [N, lookback, pca_dim + embed_dim].
        Stock embedding is a one-hot-like learned representation appended to features.
        """
        if exclude_cols is None:
            exclude_cols = ["trade_date"]

        self.stock_id_map = {code: idx for idx, code in enumerate(sorted(stock_dfs.keys()))}
        num_stocks = len(self.stock_id_map)

        all_raw_features = []
        stock_meta = []

        for ts_code, df in stock_dfs.items():
            fdf = df.drop(columns=[c for c in exclude_cols if c in df.columns])
            if not self.feature_columns:
                self.feature_columns = fdf.columns.tolist()
            features = fdf.values.astype(np.float32)
            close_idx = self.feature_columns.index(self.target_col)
            close_prices = features[:, close_idx].copy()
            all_raw_features.append(features)
            stock_meta.append({
                "ts_code": ts_code,
                "stock_id": self.stock_id_map[ts_code],
                "features": features,
                "close_prices": close_prices,
                "n": len(features),
            })

        train_portions = []
        for m in stock_meta:
            n = m["n"]
            ts = n - int(n * self.test_ratio) - int(n * self.val_ratio)
            train_portions.append(m["features"][:ts])

        combined_train = np.concatenate(train_portions, axis=0)
        del train_portions, all_raw_features

        self.feature_scaler.fit(combined_train)

        n_comp = min(self.pca_components, combined_train.shape[1])
        scaled_train = self.feature_scaler.transform(combined_train)
        self.pca = PCA(n_components=n_comp)
        self.pca.fit(scaled_train)
        del combined_train, scaled_train

        explained = sum(self.pca.explained_variance_ratio_) * 100
        logger.info(f"多股票PCA: {n_comp}维, 保留方差 {explained:.1f}%, 股票数={num_stocks}")

        embed_dim = min(16, max(4, num_stocks // 100))

        train_Xs, train_ys = [], []
        val_Xs, val_ys = [], []
        test_Xs, test_ys = [], []
        test_bps = []
        all_train_returns = []

        for m in stock_meta:
            n = m["n"]
            test_size = int(n * self.test_ratio)
            val_size = int(n * self.val_ratio)
            train_size = n - val_size - test_size

            if train_size < self.lookback + self.predict_steps + 5:
                continue

            scaled = self.feature_scaler.transform(m["features"])
            pca_feat = self.pca.transform(scaled).astype(np.float32)

            sid_feature = np.full((n, embed_dim), m["stock_id"] / max(num_stocks, 1), dtype=np.float32)
            combined_feat = np.concatenate([pca_feat, sid_feature], axis=1)

            X, y, bp = self._create_return_sequences(combined_feat, m["close_prices"])
            if len(X) == 0:
                continue

            te = max(1, train_size - self.lookback - self.predict_steps + 1)
            ve = max(te + 1, train_size + val_size - self.lookback - self.predict_steps + 1)

            train_Xs.append(X[:te])
            train_ys.append(y[:te])
            all_train_returns.append(y[:te])

            if ve > te:
                val_Xs.append(X[te:ve])
                val_ys.append(y[te:ve])

            if len(X) > ve:
                test_Xs.append(X[ve:])
                test_ys.append(y[ve:])
                test_bps.append(bp[ve:])

        if not train_Xs:
            raise ValueError("无有效训练数据")

        train_X = np.concatenate(train_Xs)
        train_y = np.concatenate(train_ys)
        val_X = np.concatenate(val_Xs) if val_Xs else np.empty((0, self.lookback, n_comp + embed_dim), dtype=np.float32)
        val_y = np.concatenate(val_ys) if val_ys else np.empty((0, self.predict_steps), dtype=np.float32)
        test_X = np.concatenate(test_Xs) if test_Xs else np.empty((0, self.lookback, n_comp + embed_dim), dtype=np.float32)
        test_y = np.concatenate(test_ys) if test_ys else np.empty((0, self.predict_steps), dtype=np.float32)
        self.test_base_prices = np.concatenate(test_bps) if test_bps else np.array([])

        shuffle_idx = np.random.permutation(len(train_X))
        train_X = train_X[shuffle_idx]
        train_y = train_y[shuffle_idx]

        combined_train_returns = np.concatenate(all_train_returns)
        self.target_scaler.fit(combined_train_returns)
        train_y = self.target_scaler.transform(train_y).astype(np.float32)
        val_y = self.target_scaler.transform(val_y).astype(np.float32) if len(val_y) > 0 else val_y
        test_y = self.target_scaler.transform(test_y).astype(np.float32) if len(test_y) > 0 else test_y

        logger.info(
            f"多股票数据准备完成: {num_stocks}只股票, 特征维度={train_X.shape[2]}, "
            f"训练={len(train_X)}, 验证={len(val_X)}, 测试={len(test_X)}"
        )
        return train_X, train_y, val_X, val_y, test_X, test_y

    # ------------------------------------------------------------------
    # Multi-stock chunked mode (low memory, memmap-backed)
    # ------------------------------------------------------------------
    def prepare_multi_stock_data_chunked(
        self, stock_dfs: Dict[str, pd.DataFrame], chunk_size: int = 500,
        exclude_cols: list = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        与 prepare_multi_stock_data 功能相同，但分批处理以控制内存峰值。
        使用 IncrementalPCA + partial_fit 增量拟合，序列数据写入磁盘 memmap。
        峰值内存 ≈ chunk_size 只股票的处理量，不随总股票数增长。
        """
        if exclude_cols is None:
            exclude_cols = ["trade_date"]

        self._temp_dir = str(MODEL_DIR / "temp_memmap")
        os.makedirs(self._temp_dir, exist_ok=True)

        self.stock_id_map = {code: idx for idx, code in enumerate(sorted(stock_dfs.keys()))}
        num_stocks = len(self.stock_id_map)
        embed_dim = min(16, max(4, num_stocks // 100))
        codes = sorted(stock_dfs.keys())

        # --- Pass 1: incremental fit scaler + PCA ---
        logger.info(f"Pass 1/2: 增量拟合 Scaler + PCA ({num_stocks}只股票, chunk={chunk_size})")
        self.feature_scaler = StandardScaler()

        for ci in range(0, len(codes), chunk_size):
            chunk_codes = codes[ci:ci + chunk_size]
            train_portions = []
            for ts_code in chunk_codes:
                df = stock_dfs[ts_code]
                fdf = df.drop(columns=[c for c in exclude_cols if c in df.columns])
                if not self.feature_columns:
                    self.feature_columns = fdf.columns.tolist()
                features = fdf.values.astype(np.float32)
                n = len(features)
                ts = n - int(n * self.test_ratio) - int(n * self.val_ratio)
                if ts > 0:
                    train_portions.append(features[:ts])
            if train_portions:
                combined = np.concatenate(train_portions, axis=0)
                self.feature_scaler.partial_fit(combined)
                del combined
            del train_portions
            gc.collect()

        n_comp = min(self.pca_components, len(self.feature_columns))
        ipca = IncrementalPCA(n_components=n_comp)

        for ci in range(0, len(codes), chunk_size):
            chunk_codes = codes[ci:ci + chunk_size]
            train_portions = []
            for ts_code in chunk_codes:
                df = stock_dfs[ts_code]
                fdf = df.drop(columns=[c for c in exclude_cols if c in df.columns])
                features = fdf.values.astype(np.float32)
                n = len(features)
                ts = n - int(n * self.test_ratio) - int(n * self.val_ratio)
                if ts > 0:
                    train_portions.append(features[:ts])
            if train_portions:
                combined = np.concatenate(train_portions, axis=0)
                scaled = self.feature_scaler.transform(combined)
                if len(scaled) >= n_comp:
                    ipca.partial_fit(scaled)
                del combined, scaled
            del train_portions
            gc.collect()
            logger.info(f"  Scaler+PCA 拟合进度: {min(ci + chunk_size, len(codes))}/{len(codes)}")

        self.pca = ipca
        explained = sum(self.pca.explained_variance_ratio_) * 100
        logger.info(f"  分批PCA: {n_comp}维, 保留方差 {explained:.1f}%")

        # --- Count sequences to pre-allocate memmap ---
        feat_dim = n_comp + embed_dim
        stock_seq_info = {}
        total_train = total_val = total_test = 0

        for ts_code in codes:
            df = stock_dfs[ts_code]
            fdf = df.drop(columns=[c for c in exclude_cols if c in df.columns])
            n = len(fdf)
            test_size = int(n * self.test_ratio)
            val_size = int(n * self.val_ratio)
            train_size = n - val_size - test_size
            if train_size < self.lookback + self.predict_steps + 5:
                continue
            total_seqs = n - self.lookback - self.predict_steps + 1
            if total_seqs <= 0:
                continue
            te = max(1, train_size - self.lookback - self.predict_steps + 1)
            ve = max(te + 1, train_size + val_size - self.lookback - self.predict_steps + 1)
            tc = te
            vc = max(0, ve - te)
            tec = max(0, total_seqs - ve)
            stock_seq_info[ts_code] = (tc, vc, tec)
            total_train += tc
            total_val += vc
            total_test += tec

        if total_train == 0:
            raise ValueError("无有效训练数据")

        logger.info(f"  序列统计: 训练={total_train}, 验证={total_val}, 测试={total_test}, 特征={feat_dim}")

        # --- Pass 2: create sequences → memmap ---
        logger.info(f"Pass 2/2: 分批生成序列 → memmap")
        td = self._temp_dir
        train_X_mm = np.memmap(os.path.join(td, "train_X.dat"), dtype=np.float32,
                               mode='w+', shape=(total_train, self.lookback, feat_dim))
        train_y_mm = np.memmap(os.path.join(td, "train_y.dat"), dtype=np.float32,
                               mode='w+', shape=(total_train, self.predict_steps))
        val_X_mm = np.memmap(os.path.join(td, "val_X.dat"), dtype=np.float32,
                             mode='w+', shape=(max(total_val, 1), self.lookback, feat_dim))
        val_y_mm = np.memmap(os.path.join(td, "val_y.dat"), dtype=np.float32,
                             mode='w+', shape=(max(total_val, 1), self.predict_steps))
        test_X_mm = np.memmap(os.path.join(td, "test_X.dat"), dtype=np.float32,
                              mode='w+', shape=(max(total_test, 1), self.lookback, feat_dim))
        test_y_mm = np.memmap(os.path.join(td, "test_y.dat"), dtype=np.float32,
                              mode='w+', shape=(max(total_test, 1), self.predict_steps))

        tr_off = val_off = te_off = 0
        test_bps_list = []

        for ci in range(0, len(codes), chunk_size):
            chunk_codes = codes[ci:ci + chunk_size]
            for ts_code in chunk_codes:
                if ts_code not in stock_seq_info:
                    continue
                df = stock_dfs[ts_code]
                fdf = df.drop(columns=[c for c in exclude_cols if c in df.columns])
                features = fdf.values.astype(np.float32)
                close_idx = self.feature_columns.index(self.target_col)
                close_prices = features[:, close_idx].copy()
                n = len(features)

                scaled = self.feature_scaler.transform(features)
                pca_feat = self.pca.transform(scaled).astype(np.float32)
                stock_id = self.stock_id_map[ts_code]
                sid_feat = np.full((n, embed_dim), stock_id / max(num_stocks, 1), dtype=np.float32)
                combined_feat = np.concatenate([pca_feat, sid_feat], axis=1)

                X, y, bp = self._create_return_sequences(combined_feat, close_prices)
                if len(X) == 0:
                    continue

                tc, vc, tec = stock_seq_info[ts_code]
                if tc > 0:
                    train_X_mm[tr_off:tr_off + tc] = X[:tc]
                    train_y_mm[tr_off:tr_off + tc] = y[:tc]
                    tr_off += tc
                if vc > 0:
                    val_X_mm[val_off:val_off + vc] = X[tc:tc + vc]
                    val_y_mm[val_off:val_off + vc] = y[tc:tc + vc]
                    val_off += vc
                if tec > 0:
                    test_X_mm[te_off:te_off + tec] = X[tc + vc:tc + vc + tec]
                    test_y_mm[te_off:te_off + tec] = y[tc + vc:tc + vc + tec]
                    test_bps_list.append(bp[tc + vc:tc + vc + tec])
                    te_off += tec

                del X, y, bp, scaled, pca_feat, combined_feat
            gc.collect()
            logger.info(f"  序列生成进度: {min(ci + chunk_size, len(codes))}/{len(codes)}")

        train_X_mm.flush(); train_y_mm.flush()
        val_X_mm.flush(); val_y_mm.flush()
        test_X_mm.flush(); test_y_mm.flush()

        self.test_base_prices = np.concatenate(test_bps_list) if test_bps_list else np.array([])

        # Fit target_scaler incrementally on training returns
        self.target_scaler = StandardScaler()
        step = 100000
        for i in range(0, total_train, step):
            self.target_scaler.partial_fit(train_y_mm[i:min(i + step, total_train)])

        for i in range(0, total_train, step):
            end = min(i + step, total_train)
            train_y_mm[i:end] = self.target_scaler.transform(train_y_mm[i:end]).astype(np.float32)
        if total_val > 0:
            for i in range(0, total_val, step):
                end = min(i + step, total_val)
                val_y_mm[i:end] = self.target_scaler.transform(val_y_mm[i:end]).astype(np.float32)
        if total_test > 0:
            for i in range(0, total_test, step):
                end = min(i + step, total_test)
                test_y_mm[i:end] = self.target_scaler.transform(test_y_mm[i:end]).astype(np.float32)
        train_y_mm.flush(); val_y_mm.flush(); test_y_mm.flush()

        train_X = train_X_mm[:total_train]
        train_y = train_y_mm[:total_train]
        val_X = val_X_mm[:total_val] if total_val > 0 else np.empty((0, self.lookback, feat_dim), dtype=np.float32)
        val_y = val_y_mm[:total_val] if total_val > 0 else np.empty((0, self.predict_steps), dtype=np.float32)
        test_X = test_X_mm[:total_test] if total_test > 0 else np.empty((0, self.lookback, feat_dim), dtype=np.float32)
        test_y = test_y_mm[:total_test] if total_test > 0 else np.empty((0, self.predict_steps), dtype=np.float32)

        logger.info(
            f"分批数据准备完成: {num_stocks}只股票, 特征维度={feat_dim}, "
            f"训练={total_train}, 验证={total_val}, 测试={total_test}"
        )
        return train_X, train_y, val_X, val_y, test_X, test_y

    def cleanup_temp_memmap(self):
        """清理 memmap 临时文件"""
        if hasattr(self, '_temp_dir') and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.info(f"已清理临时目录: {self._temp_dir}")

    # ------------------------------------------------------------------
    # Common methods
    # ------------------------------------------------------------------
    def _create_return_sequences(
        self, features: np.ndarray, close_prices: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        X, y, bp = [], [], []
        max_i = len(features) - self.lookback - self.predict_steps + 1
        for i in range(max_i):
            X.append(features[i: i + self.lookback])
            base = close_prices[i + self.lookback - 1]
            returns = []
            for j in range(self.predict_steps):
                future = close_prices[i + self.lookback + j]
                returns.append((future - base) / (base + 1e-8))
            y.append(returns)
            bp.append(base)
        return (
            np.array(X, dtype=np.float32),
            np.array(y, dtype=np.float32),
            np.array(bp, dtype=np.float32),
        )

    def inverse_transform_target(
        self, scaled_values: np.ndarray, base_prices: np.ndarray = None
    ) -> np.ndarray:
        bp = base_prices if base_prices is not None else self.test_base_prices
        if scaled_values.ndim == 1:
            scaled_values = scaled_values.reshape(-1, self.predict_steps)
        returns = self.target_scaler.inverse_transform(scaled_values)
        if bp is not None and len(bp) > 0:
            prices = bp.reshape(-1, 1) * (1 + returns)
            return prices.flatten()
        return returns.flatten()

    def save_scalers(self, ts_code: str, model_type: str, predict_steps: int) -> Tuple[str, str]:
        prefix = f"{ts_code}_{model_type}_step{predict_steps}"
        feat_path = str(MODEL_DIR / f"{prefix}_feature_scaler.pkl")
        target_path = str(MODEL_DIR / f"{prefix}_target_scaler.pkl")
        pca_path = str(MODEL_DIR / f"{prefix}_pca.pkl")

        joblib.dump(self.feature_scaler, feat_path)
        joblib.dump(self.target_scaler, target_path)
        if self.pca is not None:
            joblib.dump(self.pca, pca_path)

        if self.stock_id_map:
            map_path = str(MODEL_DIR / f"{prefix}_stock_id_map.json")
            with open(map_path, "w") as f:
                json.dump(self.stock_id_map, f)

        logger.info(f"标准化器+PCA已保存: {prefix}")
        return feat_path, target_path

    def load_scalers(self, feat_path: str, target_path: str):
        self.feature_scaler = joblib.load(feat_path)
        self.target_scaler = joblib.load(target_path)

        pca_path = feat_path.replace("_feature_scaler.pkl", "_pca.pkl")
        if os.path.exists(pca_path):
            self.pca = joblib.load(pca_path)

        map_path = feat_path.replace("_feature_scaler.pkl", "_stock_id_map.json")
        if os.path.exists(map_path):
            with open(map_path) as f:
                self.stock_id_map = json.load(f)

        logger.info("标准化器+PCA已加载")

    def prepare_predict_input(self, df: pd.DataFrame, ts_code: str = None, exclude_cols: list = None) -> np.ndarray:
        if exclude_cols is None:
            exclude_cols = ["trade_date"]

        feature_df = df.drop(columns=[c for c in exclude_cols if c in df.columns])
        if list(feature_df.columns) != self.feature_columns:
            feature_df = feature_df[self.feature_columns]

        features = feature_df.values.astype(np.float32)
        close_idx = self.feature_columns.index(self.target_col)
        last_close = features[-1, close_idx]
        self.test_base_prices = np.array([last_close])

        scaled = self.feature_scaler.transform(features)
        if self.pca is not None:
            scaled = self.pca.transform(scaled).astype(np.float32)

        if self.stock_id_map and ts_code:
            num_stocks = max(len(self.stock_id_map), 1)
            embed_dim = min(16, max(4, num_stocks // 100))
            sid = self.stock_id_map.get(ts_code, 0)
            sid_feature = np.full((len(scaled), embed_dim), sid / max(num_stocks, 1), dtype=np.float32)
            scaled = np.concatenate([scaled, sid_feature], axis=1)

        X = scaled[-self.lookback:].reshape(1, self.lookback, -1)
        return X
