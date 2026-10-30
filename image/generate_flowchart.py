from graphviz import Digraph

dot = Digraph(
    name="research_flowchart",
    format="png",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "white",
        "dpi": "300",
        "margin": "0.5",
        "ranksep": "0.8",
        "nodesep": "0.5",
    },
    node_attr={
        "fontname": "SimSun",
        "fontsize": "16",
        "fontcolor": "black",
        "color": "black",
        "shape": "box",
        "style": "rounded",
        "penwidth": "1.5",
    },
    edge_attr={
        "fontname": "SimSun",
        "fontsize": "14",
        "color": "black",
        "arrowsize": "1.0",
        "penwidth": "1.2",
    },
)

dot.node("ch1", "引言", width="2.5", height="0.6")

dot.node(
    "ch2",
    "相关技术及理论基础\n（技术指标体系、PCA降维、BiLSTM模型、\nTransformer模型、TFT模型）",
    width="6",
    height="1.0",
)

dot.node("ch3", "模型设计与训练", width="3", height="0.6")

dot.node("ch3_1", "数据集介绍", width="1.8", height="0.55")
dot.node("ch3_2", "数据预处理", width="1.8", height="0.55")
dot.node("ch3_3", "评估指标选择", width="1.8", height="0.55")
dot.node("ch3_4", "模型训练结果", width="1.8", height="0.55")

dot.node(
    "ch3_model",
    "股票价格预测模型\n（BiLSTM / Transformer / TFT 对比）",
    width="6",
    height="0.9",
)

dot.node("ch4", "股票智能预测系统", width="3.5", height="0.6")

dot.node("ch4_1", "系统需求分析", width="1.8", height="0.55")
dot.node("ch4_2", "系统设计", width="1.8", height="0.55")
dot.node("ch4_3", "系统实现", width="1.8", height="0.55")

dot.node("ch5", "系统测试", width="2.5", height="0.6")

dot.node("end", "结论", width="2", height="0.6")

dot.edge("ch1", "ch2")
dot.edge("ch2", "ch3")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("ch3_1")
    s.node("ch3_2")
    s.node("ch3_3")
    s.node("ch3_4")

dot.edge("ch3", "ch3_1")
dot.edge("ch3", "ch3_2")
dot.edge("ch3", "ch3_3")
dot.edge("ch3", "ch3_4")

dot.edge("ch3_1", "ch3_model")
dot.edge("ch3_2", "ch3_model")
dot.edge("ch3_3", "ch3_model")
dot.edge("ch3_4", "ch3_model")

dot.edge("ch3_model", "ch4")

with dot.subgraph() as s:
    s.attr(rank="same")
    s.node("ch4_1")
    s.node("ch4_2")
    s.node("ch4_3")

dot.edge("ch4", "ch4_1")
dot.edge("ch4", "ch4_2")
dot.edge("ch4", "ch4_3")

dot.edge("ch4_1", "ch5")
dot.edge("ch4_2", "ch5")
dot.edge("ch4_3", "ch5")

dot.edge("ch5", "end")

dot.render("research_flowchart", directory=".", cleanup=True, view=False)
print("流程图已生成: research_flowchart.png")
