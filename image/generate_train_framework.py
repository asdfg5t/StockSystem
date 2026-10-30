from graphviz import Digraph

dot = Digraph(
    name="train_framework",
    format="png",
    graph_attr={
        "rankdir": "LR",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.3",
        "ranksep": "1.0",
        "nodesep": "0.4",
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

dot.node("data", "A股日线\n行情数据", width="1.6", height="0.8")

dot.node(
    "preprocess",
    "数据预处理\n（特征工程、标准化、\nPCA降维、数据集划分）",
    width="2.8", height="1.0",
)

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("bilstm", "BiLSTM 模型", width="2", height="0.6")
    s.node("transformer", "Transformer 模型", width="2", height="0.6")
    s.node("tft", "TFT 模型", width="2", height="0.6")

dot.node(
    "evaluate",
    "模型评估\n（MAE / RMSE / R² /\nMAPE / 夏普比率）",
    width="2.8", height="1.0",
)

dot.edge("data", "preprocess")
dot.edge("preprocess", "bilstm")
dot.edge("preprocess", "transformer")
dot.edge("preprocess", "tft")
dot.edge("bilstm", "evaluate")
dot.edge("transformer", "evaluate")
dot.edge("tft", "evaluate")

dot.render("train_framework", directory=".", cleanup=True, view=False)
print("训练框架图已生成: train_framework.png")
