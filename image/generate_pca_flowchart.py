from graphviz import Digraph

dot = Digraph(
    name="pca_flowchart",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.4",
        "ranksep": "0.6",
        "nodesep": "0.6",
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

dot.node("input", "原始特征矩阵\nX ∈ R^(n×72)", width="3", height="0.7")

dot.node("standard", "标准化处理\n（仅在训练集上拟合）", width="3.2", height="0.7")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node(
        "mean",
        "计算均值向量 μ\n和标准差向量 σ",
        width="2.8", height="0.7",
    )
    s.node(
        "zscore",
        "Z-Score 标准化\nx' = (x − μ) / σ",
        width="2.8", height="0.7",
    )

dot.node("cov", "计算协方差矩阵\nC = (1/n) X'ᵀX'", width="3.2", height="0.7")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node(
        "eigen",
        "特征值分解\nCv = λv",
        width="2.8", height="0.7",
    )
    s.node(
        "sort",
        "按特征值降序排列\nλ₁ ≥ λ₂ ≥ … ≥ λ₇₂",
        width="3", height="0.7",
    )

dot.node(
    "select",
    "选取前 k 个主成分\n累计方差贡献率 ≥ 95%\n（k = 25）",
    width="3.5", height="0.9",
)

dot.node(
    "proj",
    "构造投影矩阵\nW = [v₁, v₂, …, v₂₅]",
    width="3.2", height="0.7",
)

dot.node("result", "降维特征矩阵\nZ = X'W ∈ R^(n×25)", width="3.2", height="0.7")

dot.node("output", "输入深度学习模型\n（BiLSTM / Transformer / TFT）", width="3.8", height="0.7")

dot.edge("input", "standard")
dot.edge("standard", "mean")
dot.edge("mean", "zscore")
dot.edge("zscore", "cov")
dot.edge("cov", "eigen")
dot.edge("eigen", "sort")
dot.edge("sort", "select")
dot.edge("select", "proj")
dot.edge("proj", "result")
dot.edge("result", "output")

dot.render("pca_flowchart", directory=".", cleanup=True, view=False)
print("PCA流程图已生成: pca_flowchart.png")
