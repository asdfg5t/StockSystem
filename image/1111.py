# -*- coding: utf-8 -*-
"""
生成毕业答辩 PPT 用的两张黑白流程图
图1: 研究背景与动机
图2: 主要研究工作（三步走）
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 11

OUT_DIR = r"E:\danzi\StockSystem\outputs"


def draw_box(ax, x, y, w, h, text, fontsize=11, bold=False,
             fill='white', edge='black', lw=1.5, radius=0.02):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.005,rounding_size={radius}",
        linewidth=lw, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(x + w / 2, y + h / 2, text,
            ha='center', va='center',
            fontsize=fontsize, fontweight=weight, color='black')


def draw_arrow(ax, x1, y1, x2, y2, lw=1.5, style='-|>'):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=18,
        linewidth=lw, color='black',
    )
    ax.add_patch(arr)


# ============================================================
# 图1: 研究背景与动机
# ============================================================
def draw_motivation():
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis('off')

    ax.text(6, 6.55, '研究背景与核心动机', ha='center', va='center',
            fontsize=18, fontweight='bold')
    ax.plot([2.5, 9.5], [6.25, 6.25], color='black', lw=1)

    draw_box(ax, 0.3, 4.2, 5.4, 1.7, '', edge='black', lw=1.5)
    ax.text(3.0, 5.55, '市场背景', ha='center', fontsize=13, fontweight='bold')
    ax.text(3.0, 5.05, '2.51 亿  A股投资者总数（2025）',
            ha='center', fontsize=11)
    ax.text(3.0, 4.65, '2743.69 万  2025年新增开户（同比+9.75%）',
            ha='center', fontsize=11)
    ax.text(3.0, 4.32, '数据量持续累积，建模需求迫切',
            ha='center', fontsize=10, style='italic', color='#444')

    draw_box(ax, 6.3, 4.2, 5.4, 1.7, '', edge='black', lw=1.5)
    ax.text(9.0, 5.55, '技术挑战', ha='center', fontsize=13, fontweight='bold')
    ax.text(9.0, 5.05, '高噪声  ·  非线性  ·  非平稳',
            ha='center', fontsize=11, fontweight='bold')
    ax.text(9.0, 4.65, '传统 ARIMA / 指数平滑 假设序列平稳',
            ha='center', fontsize=10)
    ax.text(9.0, 4.32, '面对 A股复杂特征 泛化能力不足',
            ha='center', fontsize=10, style='italic', color='#444')

    draw_arrow(ax, 3.0, 4.18, 5.0, 2.85)
    draw_arrow(ax, 9.0, 4.18, 7.0, 2.85)

    draw_box(ax, 2.5, 1.6, 7.0, 1.2, '', edge='black', lw=2.0)
    ax.text(6.0, 2.4, '研究动机', ha='center', fontsize=13, fontweight='bold')
    ax.text(6.0, 1.95,
            '验证 BiLSTM / Transformer / TFT 在 A股多步建模任务上的适用性',
            ha='center', fontsize=11)

    draw_arrow(ax, 6.0, 1.55, 6.0, 0.85)
    draw_box(ax, 3.5, 0.2, 5.0, 0.6, '面向中国A股短期收益率序列建模',
             fontsize=11, bold=True, lw=1.5)

    plt.tight_layout()
    out = f"{OUT_DIR}\\fig1_motivation.png"
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"已生成: {out}")


# ============================================================
# 图2: 主要研究工作（三步走）
# ============================================================
def draw_workflow():
    fig, ax = plt.subplots(figsize=(13, 6), dpi=200)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis('off')

    ax.text(6.5, 6.55, '主要研究工作 · 三步走', ha='center', va='center',
            fontsize=18, fontweight='bold')
    ax.plot([3.5, 9.5], [6.25, 6.25], color='black', lw=1)

    cards = [
        {
            'x': 0.3, 'title': 'STEP 1', 'name': '数据与特征体系',
            'lines': [
                'Tushare Pro  接口采集',
                '5000+ 只 A 股 / 近 3 年',
                '208,380  条时序样本',
                '72 维技术指标 → 25 主成分',
                '趋势 / 震荡 / 波动 / 量价 / 时间',
            ],
        },
        {
            'x': 4.5, 'title': 'STEP 2', 'name': '多模型对比实验',
            'lines': [
                'BiLSTM  +  Attention',
                'Transformer  Encoder-Decoder',
                'TFT  时间融合 Transformer',
                '建模步长  1 天 / 3 天 / 5 天',
                'MAE · RMSE · MAPE · R² · 准确率',
            ],
        },
        {
            'x': 8.7, 'title': 'STEP 3', 'name': '平台化落地',
            'lines': [
                'FastAPI  +  Vue 3  前后端分离',
                '数据采集 / 特征工程',
                '模型训练 / 结果分析',
                '回测验证 / 多模型对比',
                '端到端可视化系统',
            ],
        },
    ]

    card_w, card_h = 4.0, 4.4
    card_y = 1.5

    for i, c in enumerate(cards):
        x = c['x']
        draw_box(ax, x, card_y, card_w, card_h, '', lw=1.5)
        ax.plot([x, x + card_w], [card_y + card_h - 0.55,
                                  card_y + card_h - 0.55],
                color='black', lw=0.8)

        ax.text(x + 0.2, card_y + card_h - 0.3, c['title'],
                ha='left', va='center', fontsize=10, color='#666',
                fontweight='bold')
        ax.text(x + card_w / 2, card_y + card_h - 0.85, c['name'],
                ha='center', va='center',
                fontsize=13, fontweight='bold')

        for j, line in enumerate(c['lines']):
            ax.text(x + 0.25, card_y + card_h - 1.45 - j * 0.55,
                    f'·  {line}',
                    ha='left', va='center', fontsize=10.5)

    draw_arrow(ax, 4.32, card_y + card_h / 2, 4.48, card_y + card_h / 2,
               lw=2, style='-|>')
    draw_arrow(ax, 8.52, card_y + card_h / 2, 8.68, card_y + card_h / 2,
               lw=2, style='-|>')

    draw_box(ax, 1.5, 0.25, 10.0, 0.7, '', lw=1.5)
    ax.text(6.5, 0.6,
            '可复现 · 可扩展 · 可对比的端到端时序建模平台',
            ha='center', va='center', fontsize=11.5, fontweight='bold')

    plt.tight_layout()
    out = f"{OUT_DIR}\\fig2_workflow.png"
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"已生成: {out}")


if __name__ == '__main__':
    draw_motivation()
    draw_workflow()
    print('全部完成')