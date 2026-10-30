from graphviz import Digraph

dot = Digraph(
    name="tft_flowchart",
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

dot.node("gate_input", "门控输入层\nLinear + GLU", width="3", height="0.7")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("static", "静态协变量编码器\n（GRN 提取全局上下文）", width="3.2", height="0.7")
    s.node("vsn", "变量选择网络\n（VSN 特征筛选）", width="3.2", height="0.7")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("encoder", "LSTM 编码器\n（2层）", width="2.5", height="0.7")
    s.node("decoder", "LSTM 解码器\n（2层）", width="2.5", height="0.7")

dot.node("attn", "可解释多头注意力\n（4头 × 32维）", width="3.2", height="0.7")

dot.node("ff", "门控前馈网络\n（GRN + GLU + LayerNorm）", width="3.5", height="0.7")

dot.node("output", "输出投影\n128 → 64 → predict_steps", width="3.2", height="0.7")

dot.edge("input", "gate_input")
dot.edge("gate_input", "static")
dot.edge("gate_input", "vsn")
dot.edge("static", "vsn", style="dashed", label="上下文引导")
dot.edge("vsn", "encoder")
dot.edge("encoder", "decoder", label="隐藏状态传递")
dot.edge("decoder", "attn")
dot.edge("attn", "ff")
dot.edge("ff", "output")

dot.node(
    "note",
    "TFT 核心特点：\n· 变量选择：自动筛选关键特征\n· 门控残差：信息自适应流通\n· 注意力权重可解释",
    shape="note", width="3", height="1.0",
    fontsize="13", style="",
)
dot.edge("attn", "note", style="dashed", arrowhead="none", constraint="false")

dot.render("tft_flowchart", directory=".", cleanup=True, view=False)
print("TFT结构图已生成: tft_flowchart.png")
