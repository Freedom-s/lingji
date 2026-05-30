from pydantic import BaseModel,Field

class PageEvaluation(BaseModel):
    is_relevant: bool = Field(description="该页面是否包含能回答用户问题的任何相关信息")
    reason: str = Field(description="判断相关或不相关的简要理由，限30字以内")
    needs_prev_page: bool = Field(
        description="页面信息(如表格、段落)是否在开头被截断，强烈需要上一页的上下文。"
    )
    needs_next_page: bool = Field(
        description="页面信息是否在结尾未讲完，强烈需要下一页的上下文。"
    )

print(PageEvaluation.model_json_schema())