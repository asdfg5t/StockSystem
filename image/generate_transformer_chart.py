from graphviz import Digraph

dot = Digraph(
    name="transformer_structure",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.5",
        "ranksep": "0.6",
        "nodesep": "0.4",
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
        "color": "black",
        "arrowsize": "0.8",
        "penwidth": "1.0",
    },
)

dot.node("input", "输入特征序列", width="2.8", height="0.55")
dot.node("proj", "线性投影层", width="2.8", height="0.55")
dot.node("pe", "正弦位置编码", width="2.8", height="0.55")

dot.node(
    "encoder",
    "Transformer编码器 (\u00d73层)\n多头自注意力 \u2192 前馈网络\n残差连接 + 层归一化",
    width="4", height="1.0",
)

dot.node("query", "可学习查询令牌", width="2.8", height="0.55")

dot.node(
    "decoder",
    "Transformer解码器 (\u00d73层)\n自注意力 \u2192 交叉注意力 \u2192 前馈网络\n残差连接 + 层归一化",
    width="4.2", height="1.0",
)

dot.node("norm", "层归一化", width="2.8", height="0.55")
dot.node("output", "全连接输出层 \u2192 预测价格", width="3.5", height="0.55")

dot.edge("input", "proj")
dot.edge("proj", "pe")
dot.edge("pe", "encoder")
dot.edge("encoder", "decoder", label="  编码器记忆  ", fontname="SimSun", fontsize="11")
dot.edge("query", "decoder")
dot.edge("decoder", "norm")
dot.edge("norm", "output")

dot.render("transformer_structure", directory=".", cleanup=True, view=False)
print("Transformer结构图已生成: transformer_structure.png")
