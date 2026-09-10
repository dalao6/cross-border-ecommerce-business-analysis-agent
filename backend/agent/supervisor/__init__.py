"""supervisor —— 主管 Agent（SupervisorAgent）。

负责：意图识别、任务分配、HITL 人工审核决策、结果汇总。
它把任务派发给 DataSubAgent / SearchSubAgent 两个子 Agent，最终合成答案。
"""
