"""
清理旧的单股票模型文件，仅保留 universal_* 通用模型
运行前请确认通用模型已训练完成！
"""
import os
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "saved_models"


def cleanup():
    if not MODEL_DIR.exists():
        print("saved_models 目录不存在")
        return

    universal_files = list(MODEL_DIR.glob("universal_*"))
    all_files = list(MODEL_DIR.glob("*"))
    old_files = [f for f in all_files if f.is_file() and not f.name.startswith("universal_")]

    old_size = sum(f.stat().st_size for f in old_files) / 1024 / 1024 / 1024
    uni_size = sum(f.stat().st_size for f in universal_files) / 1024 / 1024

    print(f"通用模型文件: {len(universal_files)} 个 ({uni_size:.1f}MB)")
    print(f"旧单股票模型: {len(old_files)} 个 ({old_size:.2f}GB)")

    if not universal_files:
        print("\n未检测到通用模型文件，请先运行 run_universal_train.py！")
        return

    confirm = input(f"\n确认删除 {len(old_files)} 个旧模型文件，释放 {old_size:.2f}GB 空间？(y/n): ")
    if confirm.lower() != "y":
        print("已取消")
        return

    deleted = 0
    for f in old_files:
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            print(f"  删除失败: {f.name} - {e}")

    print(f"\n完成! 已删除 {deleted} 个文件, 释放约 {old_size:.2f}GB")


if __name__ == "__main__":
    cleanup()
