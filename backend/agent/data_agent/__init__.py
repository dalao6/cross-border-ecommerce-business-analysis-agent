"""data_agent —— 数据库子 Agent（DataSubAgent）。

负责所有企业数据库相关操作：召回 → NL2SQL → 校验 → 执行 → 分析，
输出结构化数据回答。不参与外部搜索与跨境平台查询。
"""
