import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# Отдельная in-memory БД для тестов
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def make_book(client, **overrides):
    payload = {"title": "Test Book", "author": "Test Author", "year": 2020, "genre": "Fiction"}
    payload.update(overrides)
    r = client.post("/api/books", json=payload)
    assert r.status_code == 201
    return r.json()


# ---------- CRUD ----------

def test_create_and_get_book(client):
    book = make_book(client)
    r = client.get(f"/api/books/{book['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Test Book"


def test_update_book(client):
    book = make_book(client)
    r = client.put(f"/api/books/{book['id']}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated"
    assert r.json()["author"] == "Test Author"  # остальные поля не тронуты


def test_delete_book(client):
    book = make_book(client)
    r = client.delete(f"/api/books/{book['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_get_missing_book_returns_404(client):
    assert client.get("/api/books/9999").status_code == 404


# ---------- Поиск и фильтрация ----------

def test_search_by_title_and_author(client):
    make_book(client, title="Dune", author="Frank Herbert", genre="Sci-Fi")
    make_book(client, title="Emma", author="Jane Austen", genre="Classic")

    r = client.get("/api/books", params={"q": "dune"})
    assert [b["title"] for b in r.json()] == ["Dune"]

    r = client.get("/api/books", params={"q": "austen"})
    assert [b["title"] for b in r.json()] == ["Emma"]


def test_filter_by_genre(client):
    make_book(client, title="A", genre="Sci-Fi")
    make_book(client, title="B", genre="Classic")
    r = client.get("/api/books", params={"genre": "Sci-Fi"})
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "A"


# ---------- Отзывы и рейтинг ----------

def test_add_review_and_average(client):
    book = make_book(client)
    client.post(f"/api/books/{book['id']}/reviews", json={"rating": 5, "text": "Great"})
    client.post(f"/api/books/{book['id']}/reviews", json={"rating": 3, "text": "OK"})

    r = client.get(f"/api/books/{book['id']}")
    assert r.json()["average_rating"] == 4.0


def test_review_validation_rejects_out_of_range(client):
    book = make_book(client)
    for bad in (0, 6):
        r = client.post(f"/api/books/{book['id']}/reviews", json={"rating": bad})
        assert r.status_code == 422


def test_review_on_missing_book_returns_404(client):
    r = client.post("/api/books/9999/reviews", json={"rating": 5})
    assert r.status_code == 404


def test_cascade_delete_removes_reviews(client):
    book = make_book(client)
    client.post(f"/api/books/{book['id']}/reviews", json={"rating": 5})
    client.delete(f"/api/books/{book['id']}")
    # После удаления книги отзывы не должны висеть в статистике
    stats = client.get("/api/stats").json()
    assert stats["total_reviews"] == 0


# ---------- Статистика ----------

def test_stats_empty(client):
    stats = client.get("/api/stats").json()
    assert stats["total_books"] == 0
    assert stats["total_reviews"] == 0
    assert stats["average_rating"] is None
    assert stats["top_genres"] == []


def test_stats_counts_and_top_genres(client):
    make_book(client, title="A", genre="Sci-Fi")
    make_book(client, title="B", genre="Sci-Fi")
    make_book(client, title="C", genre="Classic")
    stats = client.get("/api/stats").json()
    assert stats["total_books"] == 3
    assert stats["top_genres"][0] == {"genre": "Sci-Fi", "count": 2}


# ---------- Граничные случаи ----------

def test_year_validation(client):
    r = client.post("/api/books", json={"title": "X", "author": "Y", "year": 3000})
    assert r.status_code == 422


def test_empty_title_rejected(client):
    r = client.post("/api/books", json={"title": "", "author": "Y"})
    assert r.status_code == 422
