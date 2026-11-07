"""Store lightweight answer ratings for evaluation."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.db import get_postgres
from app.security.auth import TokenClaims, current_user

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackInput(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=12000)
    rating: Literal["up", "down"]
    citations: list[str] = Field(default_factory=list, max_length=30)


@router.post("")
async def submit_feedback(data: FeedbackInput, user: TokenClaims = Depends(current_user)):
    pool = get_postgres()
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO feedback (user_id, tenant_id, question, answer, rating, citations)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING feedback_id""",
            (user.user_id, user.tenant_id, data.question, data.answer, data.rating, data.citations),
        )
        row = await cursor.fetchone()
    return {"feedback_id": row["feedback_id"], "saved": True}
