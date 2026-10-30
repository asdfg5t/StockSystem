import os
import gc
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import MODEL_DIR
from app.models.db_models import TrainTask, TrainMetric, ModelFile
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.dl_models.bilstm import BiLSTMModel
from app.dl_models.transformer import TransformerModel
from app.dl_models.tft import TemporalFusionTransformer
from app.utils.logger import get_logger

logger = get_logger("train")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _cleanup_gpu():
    """释放 GPU/CPU 内存"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _build_model(model_type: str, input_size: int, predict_steps: int, params: dict = None):
    params = params or {}
    if model_type == "BiLSTM":
        return BiLSTMModel(
            input_size=input_size,
            hidden_size=params.get("hidden_size", 256),
            num_layers=params.get("num_layers", 2),
            dropout=params.get("dropout", 0.15),
            predict_steps=predict_steps,
        )
    elif model_type == "Transformer":
        return TransformerModel(
            input_size=input_size,
            d_model=params.get("d_model", 256),
            nhead=params.get("nhead", 8),
            num_encoder_layers=params.get("num_encoder_layers", 3),
            num_decoder_layers=params.get("num_decoder_layers", 3),
            dim_feedforward=params.get("dim_feedforward", 512),
            dropout=params.get("dropout", 0.1),
            predict_steps=predict_steps,
        )
    elif model_type == "TFT":
        return TemporalFusionTransformer(
            input_size=input_size,
            hidden_size=params.get("hidden_size", 256),
            num_heads=params.get("num_heads", 8),
            num_encoder_layers=params.get("num_encoder_layers", 2),
            num_decoder_layers=params.get("num_decoder_layers", 2),
            dropout=params.get("dropout", 0.1),
            attention_dropout=params.get("attention_dropout", 0.1),
            predict_steps=predict_steps,
        )
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


def run_training(db: Session, task_id: int):
    """执行完整训练流程"""
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if not task:
        logger.error(f"训练任务 {task_id} 不存在")
        return
    task.status = "running"
    task.started_at = datetime.now()
    db.commit()

    try:
        logger.info(
            f"开始训练: {task.model_type} | {task.ts_code} | "
            f"步长={task.predict_steps} | epochs={task.epochs}"
        )

        feature_df = compute_features(
            db, task.ts_code, task.train_start_date, task.train_end_date
        )
        if feature_df.empty:
            raise ValueError(f"股票 {task.ts_code} 特征数据为空")

        processor = TimeSeriesProcessor(
            lookback=task.lookback_window,
            predict_steps=task.predict_steps,
            target_col="close",
            val_ratio=float(task.val_ratio),
            test_ratio=float(task.test_ratio),
            pca_components=25,
        )

        train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare_data(feature_df)

        input_size = train_X.shape[2]
        model = _build_model(task.model_type, input_size, task.predict_steps)
        model = model.to(DEVICE)

        train_dataset = TensorDataset(
            torch.FloatTensor(train_X), torch.FloatTensor(train_y)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(val_X), torch.FloatTensor(val_y)
        )
        train_loader = DataLoader(
            train_dataset, batch_size=task.batch_size, shuffle=True
        )
        val_loader = DataLoader(
            val_dataset, batch_size=task.batch_size, shuffle=False
        )

        criterion = nn.SmoothL1Loss()
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=float(task.learning_rate), weight_decay=1e-4
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=10, T_mult=2, eta_min=1e-6
        )

        best_val_loss = float("inf")
        patience_counter = 0
        early_stop_patience = 25
        start_epoch = 1
        model_save_path = str(
            MODEL_DIR /
            f"{task.ts_code}_{task.model_type}_step{task.predict_steps}_best.pth"
        )
        checkpoint_path = str(
            MODEL_DIR /
            f"{task.ts_code}_{task.model_type}_step{task.predict_steps}_checkpoint.pth"
        )

        if os.path.exists(checkpoint_path) and task.current_epoch and task.current_epoch > 0:
            try:
                ckpt = torch.load(checkpoint_path, map_location=DEVICE)
                model.load_state_dict(ckpt["model_state"])
                optimizer.load_state_dict(ckpt["optimizer_state"])
                scheduler.load_state_dict(ckpt["scheduler_state"])
                start_epoch = ckpt["epoch"] + 1
                best_val_loss = ckpt.get("best_val_loss", float("inf"))
                patience_counter = ckpt.get("patience_counter", 0)
                logger.info(
                    f"断点续训: 从Epoch {start_epoch}继续 | "
                    f"Best Val Loss={best_val_loss:.6f} | Patience={patience_counter}"
                )
            except Exception as e:
                logger.warning(f"加载checkpoint失败, 从头开始训练: {e}")
                start_epoch = 1
                best_val_loss = float("inf")
                patience_counter = 0

        for epoch in range(start_epoch, task.epochs + 1):
            train_loss, train_mae, train_rmse = _train_epoch(
                model, train_loader, criterion, optimizer
            )
            val_loss, val_mae, val_rmse = _validate_epoch(model, val_loader, criterion)

            scheduler.step()
            current_lr = optimizer.param_groups[0]["lr"]

            metric = TrainMetric(
                task_id=task_id,
                epoch=epoch,
                train_loss=round(train_loss, 6),
                val_loss=round(val_loss, 6),
                train_mae=round(train_mae, 6),
                val_mae=round(val_mae, 6),
                train_rmse=round(train_rmse, 6),
                val_rmse=round(val_rmse, 6),
                learning_rate=current_lr,
            )
            db.add(metric)

            task.current_epoch = epoch
            db.commit()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(model.state_dict(), model_save_path)
                task.best_val_loss = round(best_val_loss, 6)
                db.commit()
                logger.info(
                    f"Epoch {epoch}: 新最优 | Val Loss={val_loss:.6f} | "
                    f"Val MAE={val_mae:.6f} | Val RMSE={val_rmse:.6f} | 模型已保存"
                )
            else:
                patience_counter += 1

            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "best_val_loss": best_val_loss,
                "patience_counter": patience_counter,
            }, checkpoint_path)

            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}/{task.epochs} | "
                    f"Train[Loss={train_loss:.6f} MAE={train_mae:.6f} RMSE={train_rmse:.6f}] | "
                    f"Val[Loss={val_loss:.6f} MAE={val_mae:.6f} RMSE={val_rmse:.6f}] | "
                    f"LR={current_lr:.2e} | Patience={patience_counter}/{early_stop_patience}"
                )

            if patience_counter >= early_stop_patience:
                logger.info(f"早停触发: 连续 {early_stop_patience} 轮验证损失未改善, 停在 Epoch {epoch}")
                break

        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            logger.info("训练完成, 已清理checkpoint文件")

        feat_scaler_path, target_scaler_path = processor.save_scalers(
            task.ts_code, task.model_type, task.predict_steps
        )

        model.load_state_dict(torch.load(model_save_path, map_location=DEVICE))
        model.eval()

        from app.services.evaluator import evaluate_model
        test_dataset = TensorDataset(
            torch.FloatTensor(test_X), torch.FloatTensor(test_y)
        )
        test_loader = DataLoader(
            test_dataset, batch_size=task.batch_size, shuffle=False
        )
        metrics = evaluate_model(model, test_loader, processor, DEVICE)

        evaluate_and_save(
            db, task, metrics, processor, test_X, test_y
        )

        file_size = os.path.getsize(model_save_path) if os.path.exists(model_save_path) else 0
        model_file = ModelFile(
            train_task_id=task_id,
            model_type=task.model_type,
            ts_code=task.ts_code,
            predict_steps=task.predict_steps,
            file_path=model_save_path,
            scaler_path=json.dumps({
                "feature": feat_scaler_path,
                "target": target_scaler_path,
            }),
            feature_config=json.dumps(processor.feature_columns),
            metrics=json.dumps(metrics),
            is_best=1,
            file_size=file_size,
        )
        db.add(model_file)

        task.status = "completed"
        task.model_path = model_save_path
        task.finished_at = datetime.now()
        db.commit()

        logger.info(
            f"训练完成: {task.model_type} | {task.ts_code} | "
            f"最优验证损失: {best_val_loss:.6f} | "
            f"测试 MAE: {metrics.get('mae', 'N/A')}"
        )

    except Exception as e:
        error_msg = str(e).replace("{", "{{").replace("}", "}}")
        logger.error(f"训练失败: {error_msg}", exc_info=True)
        try:
            db.rollback()
            task.status = "failed"
            task.error_msg = str(e)[:2000]
            task.finished_at = datetime.now()
            db.commit()
        except Exception:
            logger.error("保存失败状态时出错", exc_info=True)
    finally:
        _cleanup_gpu()


def _train_epoch(model, loader, criterion, optimizer):
    model.train()
    total_loss = 0
    total_mae = 0
    total_mse = 0
    count = 0

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(DEVICE)
        y_batch = y_batch.to(DEVICE)

        optimizer.zero_grad()
        output = model(X_batch)
        loss = criterion(output, y_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        batch_n = len(X_batch)
        total_loss += loss.item() * batch_n
        total_mae += torch.mean(torch.abs(output - y_batch)).item() * batch_n
        total_mse += torch.mean((output - y_batch) ** 2).item() * batch_n
        count += batch_n

    if count == 0:
        return 0.0, 0.0, 0.0
    avg_loss = total_loss / count
    avg_mae = total_mae / count
    avg_rmse = (total_mse / count) ** 0.5
    return avg_loss, avg_mae, avg_rmse


def _validate_epoch(model, loader, criterion):
    model.eval()
    total_loss = 0
    total_mae = 0
    total_mse = 0
    count = 0

    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            y_batch = y_batch.to(DEVICE)
            output = model(X_batch)
            loss = criterion(output, y_batch)
            batch_n = len(X_batch)
            total_loss += loss.item() * batch_n
            total_mae += torch.mean(torch.abs(output - y_batch)).item() * batch_n
            total_mse += torch.mean((output - y_batch) ** 2).item() * batch_n
            count += batch_n

    if count == 0:
        return 0.0, 0.0, 0.0
    avg_loss = total_loss / count
    avg_mae = total_mae / count
    avg_rmse = (total_mse / count) ** 0.5
    return avg_loss, avg_mae, avg_rmse


def evaluate_and_save(db, task, metrics, processor, test_X, test_y):
    from app.models.db_models import EvaluateResult
    import json

    actual = processor.inverse_transform_target(test_y.flatten())
    model_path = str(
        MODEL_DIR /
        f"{task.ts_code}_{task.model_type}_step{task.predict_steps}_best.pth"
    )
    model = _build_model(
        task.model_type,
        test_X.shape[2],
        task.predict_steps,
    )
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model = model.to(DEVICE)
    model.eval()

    with torch.no_grad():
        preds = model(torch.FloatTensor(test_X).to(DEVICE))
        preds = preds.cpu().numpy().flatten()

    predicted = processor.inverse_transform_target(preds)

    eval_result = EvaluateResult(
        train_task_id=task.id,
        model_type=task.model_type,
        ts_code=task.ts_code,
        predict_steps=task.predict_steps,
        dataset_type="test",
        mae=metrics.get("mae"),
        mse=metrics.get("mse"),
        rmse=metrics.get("rmse"),
        mape=metrics.get("mape"),
        smape=metrics.get("smape"),
        r2=metrics.get("r2"),
        direction_accuracy=metrics.get("direction_accuracy"),
        max_error=metrics.get("max_error"),
        median_ae=metrics.get("median_ae"),
        explained_variance=metrics.get("explained_variance"),
        pearson_corr=metrics.get("pearson_corr"),
        accuracy_1pct=metrics.get("accuracy_1pct"),
        accuracy_3pct=metrics.get("accuracy_3pct"),
        accuracy_5pct=metrics.get("accuracy_5pct"),
        win_rate=metrics.get("win_rate"),
        profit_factor=metrics.get("profit_factor"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        max_drawdown=metrics.get("max_drawdown"),
        actual_values=json.dumps(actual.tolist()),
        predicted_values=json.dumps(predicted.tolist()),
    )
    db.add(eval_result)
    db.commit()
