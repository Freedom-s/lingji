#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
页面上下文评估模型 - 用于智能前后页召回

通过 LLM Function Calling 判断页面是否需要额外的上下文信息（前后页）
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class PageEvaluation(BaseModel):
    is_relevant: bool = Field(description="该页面是否包含能直接回答用户问题的相关信息。")
    reason: str = Field(description="判断相关性及是否需要前后页的详细思考过程，限50字以内。")
    needs_prev_page: bool = Field(
        description="【严格限制】仅当当前页开头出现了被截断的句子/表格/代码块，且缺失的前半部分对于回答用户问题是**绝对必要**时，才为 true。否则必须为 false。"
    )
    needs_next_page: bool = Field(
        description="【PDF特供限制】注意：PDF文档每页末尾发生段落截断是正常排版现象！绝对不要仅仅因为“一句话没说完”或“段落没结束”就返回 true。只有当被截断的那部分内容是【直接回答用户问题所必需的核心数据或结论】，且缺少它你将无法给出确切答案时，才允许为 true。如果被截断的内容与问题无关，或者当前页已提取的信息足够回答问题，必须为 false！"
    )


def page_evaluation_tool_schema():
    """
    生成 OpenAI function calling 格式的 tool schema

    Returns:
        dict: 符合 OpenAI function calling 格式的 tool 定义
    """
    return {
        "type": "function",
        "function": {
            "name": "evaluate_page_context",
            "description": "评估页面是否需要前后页上下文信息，用于智能召回相关页面",
            "parameters": PageEvaluation.model_json_schema()
        }
    }


def build_page_evaluation_prompt(question: str, img_base64: str):
    """
    构建页面评估的多模态 prompt

    Args:
        question: 用户问题
        img_base64: 页面图片的 base64 data URL

    Returns:
        list: 多模态消息格式，包含文本和图片
    """
    text_content = f"""用户问题：{question}

请使用 evaluate_page_context 工具评估该页面。注意：
- 只在以下情况才建议召回前后页：
  * 表格被截断（只能看到部分列或行）
  * 段落在开头被截断（缺少上文）
  * 段落在结尾未讲完（需要下文）
  * 图片说明文字被切断
- 如果页面信息完整，不要召回额外页面，避免增加不必要的 token 消耗
"""

    content_parts = [{"type": "text", "text": text_content}]
    content_parts.append({
        "type": "image_url",
        "image_url": {
            "url": img_base64,
            "detail": "auto"
        }
    })
    return content_parts
