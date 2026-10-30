from graphviz import Digraph

dot = Digraph(
    name="bilstm_flowchart",
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

dot.node("input", "输入序列\n(batch × 30 × 25)", width="3", height="0.7")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("forward", "前向 LSTM\nh→ ∈ R¹²⁸", width="2.5", height="0.7")
    s.node("backward", "后向 LSTM\nh← ∈ R¹²⁸", width="2.5", height="0.7")

dot.node("concat", "拼接 + LayerNorm\nH = [h→; h←] ∈ R²⁵⁶", width="3.2", height="0.7")

dot.node("attn", "Attention 加权聚合\nc = Σ αₜ · Hₜ", width="3.2", height="0.7")

dot.node("fc", "全连接网络\n256 → 128 → 64 → predict_steps", width="3.8", height="0.7")

dot.node("output", "预测输出 ŷ", width="2.5", height="0.6")

dot.edge("input", "forward")
dot.edge("input", "backward")
dot.edge("forward", "concat")
dot.edge("backward", "concat")
dot.edge("concat", "attn")
dot.edge("attn", "fc")
dot.edge("fc", "output")

dot.node(
    "note",
    "BiLSTM 参数：\n· 隐藏维度：128 × 2\n· 堆叠层数：2\n· Dropout：0.2",
    shape="note", width="2.5", height="1.0",
    fontsize="13", style="",
)
dot.edge("forward", "note", style="dashed", arrowhead="none", constraint="false")

dot.render("bilstm_flowchart", directory=".", cleanup=True, view=False)
print("BiLSTM结构图已生成: bilstm_flowchart.png")
