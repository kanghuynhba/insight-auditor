from pydantic import BaseModel


class SummaryRequest(BaseModel):
    summary: str
