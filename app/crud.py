from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models import Book, Review
from app.schemas import BookCreate, BookUpdate


def create_book(db: Session, data: BookCreate) -> Book:
    book = Book(**data.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def get_book(db: Session, book_id: int) -> Book | None:
    return db.get(Book, book_id)


def list_books(
    db: Session,
    search: str | None = None,
    genre: str | None = None,
) -> list[Book]:
    stmt = select(Book)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Book.title.ilike(like), Book.author.ilike(like)))
    if genre:
        stmt = stmt.where(Book.genre == genre)
    stmt = stmt.order_by(Book.title)
    return list(db.scalars(stmt).all())


def update_book(db: Session, book: Book, data: BookUpdate) -> Book:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book: Book) -> None:
    db.delete(book)
    db.commit()


def add_review(db: Session, book_id: int, rating: int, text: str | None) -> Review:
    review = Review(book_id=book_id, rating=rating, text=text)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def list_reviews(db: Session, book_id: int) -> list[Review]:
    stmt = select(Review).where(Review.book_id == book_id).order_by(Review.created_at.desc())
    return list(db.scalars(stmt).all())


def average_rating(db: Session, book_id: int) -> float | None:
    stmt = select(func.avg(Review.rating)).where(Review.book_id == book_id)
    value = db.scalar(stmt)
    return round(value, 2) if value is not None else None


def stats(db: Session) -> dict:
    total_books = db.scalar(select(func.count(Book.id))) or 0
    total_reviews = db.scalar(select(func.count(Review.id))) or 0
    avg = db.scalar(select(func.avg(Review.rating)))
    top_genres = db.execute(
        select(Book.genre, func.count(Book.id).label("cnt"))
        .where(Book.genre.isnot(None))
        .group_by(Book.genre)
        .order_by(func.count(Book.id).desc())
        .limit(5)
    ).all()
    return {
        "total_books": total_books,
        "total_reviews": total_reviews,
        "average_rating": round(avg, 2) if avg is not None else None,
        "top_genres": [{"genre": g, "count": c} for g, c in top_genres],
    }

def book_to_out(db: Session, book: Book) -> "schemas.BookOut":
    """Единая сборка BookOut с вычисленным средним рейтингом."""
    from app.schemas import BookOut

    out = BookOut.model_validate(book)
    out.average_rating = average_rating(db, book.id)
    return out


def books_with_rating(db: Session, books: list[Book]) -> list["schemas.BookOut"]:
    """Один агрегатный запрос вместо N вызовов average_rating."""
    from app.schemas import BookOut

    if not books:
        return []

    ids = [b.id for b in books]
    rows = db.execute(
        select(Review.book_id, func.avg(Review.rating))
        .where(Review.book_id.in_(ids))
        .group_by(Review.book_id)
    ).all()
    ratings = {book_id: round(avg, 2) for book_id, avg in rows}

    result = []
    for b in books:
        out = BookOut.model_validate(b)
        out.average_rating = ratings.get(b.id)
        result.append(out)
    return result
