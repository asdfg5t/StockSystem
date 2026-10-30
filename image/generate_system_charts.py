from graphviz import Digraph


def _base(name, direction="TB"):
    return Digraph(
        name=name, format="png",
        graph_attr={"rankdir": direction, "bgcolor": "white", "dpi": "300",
                    "margin": "0.4", "ranksep": "0.6", "nodesep": "0.5"},
        node_attr={"fontname": "SimSun", "fontsize": "14", "fontcolor": "black",
                   "color": "black", "shape": "box", "style": "rounded", "penwidth": "1.5"},
        edge_attr={"fontname": "SimSun", "fontsize": "12", "color": "black",
                   "arrowsize": "0.9", "penwidth": "1.2"},
    )


def chart_collect():
    """数据采集与股票展示功能流程图"""
    d = _base("collect_flow")

    d.node("start", "用户创建采集任务", width="3")

    with d.subgraph() as s:
        s.attr(rank="same")
        s.node("basic", "采集股票基础信息\n（代码/名称/行业）", width="2.8")
        s.node("daily", "采集日线行情数据\n（OHLCV/涨跌幅）", width="2.8")

    d.node("strategy", "批量采集策略\n（50只/批 + 失败重试3次）", width="3.5")

    d.node("store", "数据存储\n（MySQL + 本地TSV备份）", width="3")

    with d.subgraph() as s:
        s.attr(rank="same")
        s.node("list", "股票列表展示\n（分页/搜索/行业筛选）", width="3")
        s.node("detail", "个股详情展示\n（基本信息 + K线图）", width="3")

    d.edge("start", "basic")
    d.edge("start", "daily")
    d.edge("basic", "strategy")
    d.edge("daily", "strategy")
    d.edge("strategy", "store")
    d.edge("store", "list")
    d.edge("store", "detail")

    d.node("note", "采集特点：\n· 断点续采（增量更新）\n· 异步执行（实时进度）\n· 近3年日线数据",
           shape="note", width="2.8", fontsize="12", style="")
    d.edge("strategy", "note", style="dashed", arrowhead="none", constraint="false")

    d.render("system_collect_flow", directory=".", cleanup=True, view=False)
    print("  system_collect_flow.png")


def chart_train():
    """模型训练与预测分析功能流程图"""
    d = _base("train_flow")

    d.node("data", "行情数据 + 特征工程\n（72维技术指标）", width="3.5")

    d.node("split", "按时间顺序划分数据集\n（训练70% / 验证15% / 测试15%）", width="4.2")

    d.node("preprocess", "仅在训练集拟合标准化器与PCA\n变换验证集/测试集 → 收益率转换", width="4.5")

    d.node("config", "训练参数配置\n（模型/股票/步长/轮数/学习率）", width="3.8")

    with d.subgraph() as s:
        s.attr(rank="same")
        s.node("m1", "BiLSTM", width="1.8")
        s.node("m2", "Transformer", width="1.8")
        s.node("m3", "TFT", width="1.8")

    d.node("loop", "训练循环\n（逐轮记录Loss/MAE/RMSE）", width="3.5")

    d.node("save", "保存最优模型\n（权重 + 标准化器 + PCA）", width="3.5")

    d.node("eval", "测试集评估\n（18项指标计算）", width="3")

    d.node("predict", "预测推理\n（收益率→价格还原→结果存储）", width="3.5")

    d.edge("data", "split")
    d.edge("split", "preprocess")
    d.edge("preprocess", "config")
    d.edge("config", "m1")
    d.edge("config", "m2")
    d.edge("config", "m3")
    d.edge("m1", "loop")
    d.edge("m2", "loop")
    d.edge("m3", "loop")
    d.edge("loop", "save")
    d.edge("save", "eval")
    d.edge("eval", "predict")

    d.node("note", "训练策略：\n· AdamW + SmoothL1Loss\n· 余弦退火学习率\n· 梯度裁剪(max_norm=1.0)",
           shape="note", width="3", fontsize="12", style="")
    d.edge("loop", "note", style="dashed", arrowhead="none", constraint="false")

    d.render("system_train_flow", directory=".", cleanup=True, view=False)
    print("  system_train_flow.png")


def chart_compare():
    """多模型对比与可视化分析功能流程图"""
    d = _base("compare_flow")

    d.node("select", "用户选择\n（股票代码 + 预测步长）", width="3")

    d.node("query", "查询评估结果\n（三模型测试集指标）", width="3")

    d.node("calc", "指标提取与排序\n（MAE/RMSE/MAPE/R²）", width="3.2")

    with d.subgraph() as s:
        s.attr(rank="same")
        s.node("bar", "柱状图对比\n（分组柱状图）", width="2.5")
        s.node("line", "趋势折线图\n（多步长变化）", width="2.5")
        s.node("table", "对比表格\n（高亮最优值）", width="2.5")

    d.node("best", "标注最优模型\n输出推荐结果", width="3")

    d.edge("select", "query")
    d.edge("query", "calc")
    d.edge("calc", "bar")
    d.edge("calc", "line")
    d.edge("calc", "table")
    d.edge("bar", "best")
    d.edge("line", "best")
    d.edge("table", "best")

    d.node("note", "可视化组件：\n· ECharts 图表渲染\n· Vue 响应式更新\n· 多维度筛选切换",
           shape="note", width="2.5", fontsize="12", style="")
    d.edge("calc", "note", style="dashed", arrowhead="none", constraint="false")

    d.render("system_compare_flow", directory=".", cleanup=True, view=False)
    print("  system_compare_flow.png")


if __name__ == "__main__":
    print("生成系统功能原理图:")
    chart_collect()
    chart_train()
    chart_compare()
    print("\n全部3张原理图生成完成!")
