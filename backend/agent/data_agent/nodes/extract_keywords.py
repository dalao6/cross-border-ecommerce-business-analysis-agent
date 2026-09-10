"""
关键词抽取步骤

用 jieba 从用户自然语言问题中识别检索线索，供后续字段召回、字段取值召回和指标召回使用。
jieba 缺失时自动降级为「原问题 + 空格切分」兜底，保证离线环境不因缺依赖而中断。
"""


def extract_keywords(query: str) -> list[str]:
    """抽取用户问题中的关键词，并保留原始问题作为兜底检索入口。"""
    # 只保留更可能承载业务含义的词性，减少"的、帮我、一下"这类噪声
    allow_pos = (
        "n", "nr", "ns", "nt", "nz",   # 名词类
        "v", "vn",                      # 动词、名动词
        "a", "an",                      # 形容词
        "eng",                          # 英文（GMV、SKU、ROI 等）
        "i", "l",                       # 成语/固定短语（如"销售总额"）
    )
    keywords = []
    try:
        import jieba.analyse
        keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)
    except Exception:  # noqa: BLE001 —— jieba 未安装或抽取失败
        keywords = []

    if not keywords:
        # 兜底：按空格/标点切分，避免空关键词
        import re
        keywords = [w for w in re.split(r"[\s,，。；;、]+", query) if w]

    # 保留原始问题作为兜底，set 去重
    keywords = list(set(keywords + [query]))
    return keywords

