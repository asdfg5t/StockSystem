from graphviz import Digraph

dot = Digraph(
    name="indicator_system",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.5",
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
        "color": "black",
        "arrowsize": "0.8",
        "penwidth": "1.0",
    },
)

dot.node("root", "技术指标体系", width="3", height="0.6", fontsize="16")

dot.node("cat1", "趋势跟踪类", width="2", height="0.55")
dot.node("cat2", "震荡分析类", width="2", height="0.55")
dot.node("cat3", "波动与量价类", width="2", height="0.55")
dot.node("cat4", "市场特征类", width="2", height="0.55")
dot.node("cat5", "时间编码类", width="2", height="0.55")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("cat1")
    s.node("cat2")
    s.node("cat3")
    s.node("cat4")
    s.node("cat5")

dot.edge("root", "cat1")
dot.edge("root", "cat2")
dot.edge("root", "cat3")
dot.edge("root", "cat4")
dot.edge("root", "cat5")

dot.node(
    "d1",
    "MA (5/10/20/30/60日)\n"
    "EMA (12/26/50日)\n"
    "MACD (DIF/DEA/HIST)\n"
    "均线交叉信号\n"
    "价格偏离比",
    width="3", height="1.4", fontsize="12",
)

dot.node(
    "d2",
    "KDJ (K/D/J)\n"
    "RSI (6/12/24日)\n"
    "CCI\n"
    "ROC (5/10/20日)\n"
    "MOM (5/10/20日)",
    width="3", height="1.4", fontsize="12",
)

dot.node(
    "d3",
    "布林带 (上/中/下轨、\n带宽、百分比位置)\n"
    "ATR (14日、波幅比)\n"
    "OBV (能量潮及均线)",
    width="3", height="1.4", fontsize="12",
)

dot.node(
    "d4",
    "收益率 (1/5/10日)\n"
    "波动率 (5/10/20日)\n"
    "量变率、额变率\n"
    "振幅比、实体比\n"
    "上/下影线比\n"
    "量价相关系数",
    width="3", height="1.6", fontsize="12",
)

dot.node(
    "d5",
    "星期、日期、月份\n"
    "季度、周序号\n"
    "正弦/余弦周期编码",
    width="3", height="1.1", fontsize="12",
)

dot.edge("cat1", "d1")
dot.edge("cat2", "d2")
dot.edge("cat3", "d3")
dot.edge("cat4", "d4")
dot.edge("cat5", "d5")

dot.render("indicator_system", directory=".", cleanup=True, view=False)
print("指标体系图已生成: indicator_system.png")
