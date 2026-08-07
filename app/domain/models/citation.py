"""最终输出中的轻量 citation 模型。"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """面向用户展示和核验的轻量来源引用。

    Citation 只承载最终答案中需要展示的最小引用信息。完整 provenance 应保留在
    SourceReference 中；这里的 source 通常由 SourceReference 的 URL、typed id、title
    或 citation_text 派生。
    """

    source: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。最终答案引用的来源展示句柄，例如 URL、论文 ID、docs 标题或 citation label。"
            "当前项目中有用：ConclusionGeneratorService 会从 RunningState.retrieved_evidence_refs 可派生的 handle 中选择该值；"
            "ResponseAssemblerService 会把它输出给用户用于核验来源。该字段不是完整 SourceReference，也不应用于唯一去重持久化。"
        ),
    )
    note: str | None = Field(
        default=None,
        description=(
            "可选字段。对该 citation 的简短说明，例如它支撑了哪条结论、覆盖了哪个事实或需要注意的来源限制。"
            "当前项目中有用：ConclusionGeneratorService 可写入该字段帮助用户理解引用作用；如果没有必要说明则为 None。"
        ),
    )
