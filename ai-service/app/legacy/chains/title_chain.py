from langchain_core.output_parsers import StrOutputParser
import app.infrastructure.llm.llm
from app.prompts.title import TITLE_QA_PROMPT


def build_title_chain():
    """构建标题生成链。无 key 时返回 None。"""
    llm = app.infrastructure.llm.llm.get_llm()
    if llm is None:
        return None
    return TITLE_QA_PROMPT | llm | StrOutputParser()