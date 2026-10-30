from graphviz import Digraph

dot = Digraph(
    name="preprocess_flow",
    format="png",
    graph_attr={
        "rankdir": "LR",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.3",
        "ranksep": "0.7",
        "nodesep": "0.35",
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
        "arrowsize": "0.9",
        "penwidth": "1.2",
    },
)

dot.node("input", "原始行情数据", width="1.8", height="0.6")
dot.node("clean", "数据清洗", width="1.5", height="0.6")
dot.node("feature", "特征工程\n（72维）", width="1.5", height="0.7")
dot.node("split", "按时间顺序\n划分数据集\n（70%/15%/15%）", width="2.2", height="0.9")
dot.node("scale", "仅训练集拟合\n标准化与PCA\n再应用至全局", width="2.2", height="0.9")
dot.node("config", "优化器及\n损失函数配置", width="1.8", height="0.7")

dot.edge("input", "clean")
dot.edge("clean", "feature")
dot.edge("feature", "split")
dot.edge("split", "scale")
dot.edge("scale", "config")

dot.render("preprocess_flow", directory=".", cleanup=True, view=False)
print("数据预处理流程图已生成: preprocess_flow.png")
