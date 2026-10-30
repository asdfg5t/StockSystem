from graphviz import Digraph

# ========== 图1: 数据集特征体系 ==========
d1 = Digraph(
    name="dataset_features",
    format="png",
    graph_attr={
        "rankdir": "LR",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.3",
        "ranksep": "0.8",
        "nodesep": "0.25",
    },
    node_attr={
        "fontname": "SimSun",
        "fontsize": "14",
        "fontcolor": "black",
        "color": "black",
        "shape": "box",
        "style": "rounded",
        "penwidth": "1.5",
    },
    edge_attr={
        "fontname": "SimSun",
        "fontsize": "12",
        "color": "black",
        "arrowsize": "0.8",
        "penwidth": "1.2",
    },
)

d1.node("source", "Tushare Pro\nA股日线数据", width="2", height="0.7")

d1.node("raw", "原始行情（9维）\nOHLCV + 涨跌幅等", width="2.5", height="0.7")

with d1.subgraph() as s:
    s.attr(rank="same")
    s.node("f1", "均线系统\nMA / EMA（16维）", width="2.2", height="0.65")
    s.node("f2", "震荡指标\nMACD/KDJ/RSI/CCI（13维）", width="2.8", height="0.65")
    s.node("f3", "波动与量价\nBOLL/ATR/OBV（9维）", width="2.4", height="0.65")
    s.node("f4", "动量与时间\nROC/MOM/时间编码（25维）", width="2.8", height="0.65")

d1.node("total", "完整特征集\n（72维）", width="2", height="0.7")

d1.edge("source", "raw")
d1.edge("raw", "f1")
d1.edge("raw", "f2")
d1.edge("raw", "f3")
d1.edge("raw", "f4")
d1.edge("f1", "total")
d1.edge("f2", "total")
d1.edge("f3", "total")
d1.edge("f4", "total")

d1.render("dataset_features", directory=".", cleanup=True, view=False)
print("数据集特征体系图已生成: dataset_features.png")


# ========== 图2: 数据集划分示意图 ==========
d2 = Digraph(
    name="dataset_split",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.4",
        "ranksep": "0.6",
        "nodesep": "0.5",
    },
    node_attr={
        "fontname": "SimSun",
        "fontsize": "15",
        "fontcolor": "black",
        "color": "black",
        "shape": "box",
        "style": "rounded",
        "penwidth": "1.5",
    },
    edge_attr={
        "fontname": "SimSun",
        "fontsize": "13",
        "color": "black",
        "arrowsize": "0.9",
        "penwidth": "1.2",
    },
)

d2.node("all", "完整时序数据\n（按时间顺序排列，约724个交易日）", width="4.5", height="0.7")

with d2.subgraph() as s:
    s.attr(rank="same")
    s.node("train", "训练集（70%）\n≈507个交易日", width="2.5", height="0.7")
    s.node("val", "验证集（15%）\n≈109个交易日", width="2.5", height="0.7")
    s.node("test", "测试集（15%）\n≈109个交易日", width="2.5", height="0.7")

d2.node("fit", "仅训练集拟合\nScaler + PCA", width="2.5", height="0.7")

with d2.subgraph() as s:
    s.attr(rank="same")
    s.node("apply_val", "验证集变换\n（使用训练集参数）", width="2.8", height="0.7")
    s.node("apply_test", "测试集变换\n（使用训练集参数）", width="2.8", height="0.7")

d2.edge("all", "train")
d2.edge("all", "val")
d2.edge("all", "test")
d2.edge("train", "fit")
d2.edge("fit", "apply_val")
d2.edge("fit", "apply_test")
d2.edge("val", "apply_val", style="dashed")
d2.edge("test", "apply_test", style="dashed")

d2.render("dataset_split", directory=".", cleanup=True, view=False)
print("数据集划分示意图已生成: dataset_split.png")
