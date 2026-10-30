import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["SimSun"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.dpi"] = 300

MODELS = ["BiLSTM", "Transformer", "TFT"]
STEPS = [1, 3, 5]
COLORS = ["#2563EB", "#DC2626", "#059669"]
MARKERS = ["o", "s", "D"]

DATA = {
    1: {"BiLSTM": {"mae":0.0706,"rmse":0.0960,"mape":0.63,"r2":0.9177,"acc1":80.81},
        "Transformer": {"mae":0.0798,"rmse":0.1026,"mape":0.71,"r2":0.9060,"acc1":72.73},
        "TFT": {"mae":0.0710,"rmse":0.0960,"mape":0.63,"r2":0.9178,"acc1":82.83}},
    3: {"BiLSTM": {"mae":0.0894,"rmse":0.1159,"mape":0.79,"r2":0.8772,"acc1":69.36},
        "Transformer": {"mae":0.0911,"rmse":0.1164,"mape":0.81,"r2":0.8762,"acc1":66.33},
        "TFT": {"mae":0.0881,"rmse":0.1130,"mape":0.78,"r2":0.8834,"acc1":68.69}},
    5: {"BiLSTM": {"mae":0.1332,"rmse":0.1783,"mape":1.17,"r2":0.7012,"acc1":56.57},
        "Transformer": {"mae":0.1210,"rmse":0.1501,"mape":1.08,"r2":0.7882,"acc1":54.75},
        "TFT": {"mae":0.1039,"rmse":0.1285,"mape":0.92,"r2":0.8448,"acc1":58.79}},
}


def _bar_chart(key, ylabel, title, filename, fmt=".4f"):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = np.arange(len(STEPS))
    w = 0.22
    for i, m in enumerate(MODELS):
        vals = [DATA[s][m][key] for s in STEPS]
        bars = ax.bar(x + i*w, vals, w, label=m, color=COLORS[i],
                      edgecolor="black", linewidth=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    f"{v:{fmt}}", ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("预测步长（天）", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xticks(x + w)
    ax.set_xticklabels(["1天", "3天", "5天"], fontsize=10)
    ax.legend(fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    print(f"  {filename}")


def _line_chart(key, ylabel, title, filename, fmt=".4f", suffix=""):
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, m in enumerate(MODELS):
        vals = [DATA[s][m][key] for s in STEPS]
        ax.plot(STEPS, vals, marker=MARKERS[i], label=m,
                color=COLORS[i], linewidth=2, markersize=7)
        for s, v in zip(STEPS, vals):
            ax.annotate(f"{v:{fmt}}{suffix}", (s, v), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=9)
    ax.set_xlabel("预测步长（天）", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xticks(STEPS)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(filename, bbox_inches="tight")
    plt.close()
    print(f"  {filename}")


if __name__ == "__main__":
    print("生成论文图表:")
    _bar_chart("mae", "MAE", "不同预测步长下各模型MAE对比", "chart_mae.png")
    _bar_chart("rmse", "RMSE", "不同预测步长下各模型RMSE对比", "chart_rmse.png")
    _line_chart("mape", "MAPE (%)", "不同预测步长下各模型MAPE变化趋势", "chart_mape.png", ".2f", "%")
    _line_chart("r2", "R²", "不同预测步长下各模型R²变化趋势", "chart_r2.png")
    _bar_chart("acc1", "1%准确率 (%)", "不同预测步长下各模型1%准确率对比", "chart_acc.png", ".1f")
    _line_chart("acc1", "1%准确率 (%)", "不同预测步长下各模型1%准确率变化趋势", "chart_acc_line.png", ".1f", "%")
    print("\n全部6张图表生成完成!")
