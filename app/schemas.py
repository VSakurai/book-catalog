from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    text: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    rating: int
    text: str | None
    created_at: datetime


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=150)
    year: int | None = Field(None, ge=0, le=2100)
    genre: str | None = Field(None, max_length=80)
    description: str | None = None


class BookUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    author: str | None = Field(None, min_length=1, max_length=150)
    year: int | None = Field(None, ge=0, le=2100)
    genre: str | None = Field(None, max_length=80)
    description: str | None = None


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    year: int | None
    genre: str | None
    description: str | None
    average_rating: float | None = None
