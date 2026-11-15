from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="BookCatalog", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- HTML страницы ----------

@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str | None = None, genre: str | None = None, db: Session = Depends(get_db)):
    books = crud.list_books(db, search=q, genre=genre)
    book_views = crud.books_with_rating(db, books)
    return templates.TemplateResponse(
    request, "index.html",
    {"books": book_views, "q": q or "", "genre": genre or ""},
)


@app.post("/books")
def create_book_form(
    title: str = Form(...),
    author: str = Form(...),
    year: int | None = Form(None),
    genre: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
):
    data = schemas.BookCreate(
        title=title, author=author, year=year, genre=genre, description=description
    )
    book = crud.create_book(db, data)
    return RedirectResponse(url=f"/books/{book.id}", status_code=303)


@app.get("/books/{book_id}", response_class=HTMLResponse)
def book_detail(book_id: int, request: Request, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    out = crud.book_to_out(db, book)
    reviews = crud.list_reviews(db, book_id)
    return templates.TemplateResponse(
        request, "book.html",
        {"book": out, "reviews": reviews},
    )


@app.post("/books/{book_id}/reviews")
def add_review_form(
    book_id: int,
    rating: int = Form(..., ge=1, le=5),
    text: str | None = Form(None),
    db: Session = Depends(get_db),
):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    crud.add_review(db, book_id, rating, text)
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)


@app.post("/books/{book_id}/delete")
def delete_book_form(book_id: int, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    crud.delete_book(db, book)
    return RedirectResponse(url="/", status_code=303)


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
    request, "stats.html",
    {"stats": crud.stats(db)},
)


# ---------- REST API (для Swagger) ----------

@app.get("/api/books", response_model=list[schemas.BookOut], tags=["books"])
def api_list_books(q: str | None = None, genre: str | None = None, db: Session = Depends(get_db)):
    books = crud.list_books(db, search=q, genre=genre)
    return crud.books_with_rating(db, books)


@app.post("/api/books", response_model=schemas.BookOut, status_code=201, tags=["books"])
def api_create_book(data: schemas.BookCreate, db: Session = Depends(get_db)):
    book = crud.create_book(db, data)
    return crud.book_to_out(db, book)


@app.get("/api/books/{book_id}", response_model=schemas.BookOut, tags=["books"])
def api_get_book(book_id: int, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return crud.book_to_out(db, book)


@app.put("/api/books/{book_id}", response_model=schemas.BookOut, tags=["books"])
def api_update_book(book_id: int, data: schemas.BookUpdate, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book = crud.update_book(db, book, data)
    return crud.book_to_out(db, book)


@app.delete("/api/books/{book_id}", status_code=204, tags=["books"])
def api_delete_book(book_id: int, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    crud.delete_book(db, book)


@app.post("/api/books/{book_id}/reviews", response_model=schemas.ReviewOut, status_code=201, tags=["reviews"])
def api_add_review(book_id: int, data: schemas.ReviewCreate, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return crud.add_review(db, book_id, data.rating, data.text)


@app.get("/api/books/{book_id}/reviews", response_model=list[schemas.ReviewOut], tags=["reviews"])
def api_list_reviews(book_id: int, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return crud.list_reviews(db, book_id)


@app.get("/api/stats", tags=["stats"])
def api_stats(db: Session = Depends(get_db)):
    return crud.stats(db)
