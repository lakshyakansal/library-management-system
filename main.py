import os
from datetime import date
from urllib.parse import quote
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text, or_
from sqlalchemy.orm import declarative_base, sessionmaker

APP_TITLE = "ShelfWise Library"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./library.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    author = Column(String(150), nullable=False)
    isbn = Column(String(40), unique=True, nullable=True)
    category = Column(String(100), default="General")
    total_copies = Column(Integer, default=1, nullable=False)
    available_copies = Column(Integer, default=1, nullable=False)

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(40), default="")
    joined_on = Column(Date, default=date.today)

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    issued_on = Column(Date, default=date.today)
    due_on = Column(Date, nullable=False)
    returned_on = Column(Date, nullable=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_TITLE)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-this-secret-before-deploying"),
    same_site="lax",
    https_only=os.getenv("RENDER", "").lower() == "true",
)
BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

def db_session():
    return SessionLocal()

def require_login(request: Request):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=303, headers={"Location": "/login"})

def page(request: Request, template: str, **context):
    context.update({"request": request, "app_title": APP_TITLE, "logged_in": bool(request.session.get("logged_in"))})
    return templates.TemplateResponse(template, context)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)
    db = db_session()
    try:
        books_count = db.query(Book).count()
        titles_count = db.query(Book).count()
        copies_count = db.query(Book).with_entities(Book.total_copies).all()
        total_copies = sum(x[0] for x in copies_count)
        available_copies = sum(x[0] for x in db.query(Book).with_entities(Book.available_copies).all())
        members_count = db.query(Member).count()
        active_loans = db.query(Loan).filter(Loan.returned_on.is_(None)).count()
        overdue_count = db.query(Loan).filter(Loan.returned_on.is_(None), Loan.due_on < date.today()).count()
        recent = db.query(Loan).filter(Loan.returned_on.is_(None)).order_by(Loan.issued_on.desc()).limit(6).all()
        recent_rows = []
        for loan in recent:
            book, member = db.get(Book, loan.book_id), db.get(Member, loan.member_id)
            if book and member:
                recent_rows.append({"loan": loan, "book": book, "member": member})
        return page(request, "dashboard.html", books_count=books_count, titles_count=titles_count,
                    total_copies=total_copies, available_copies=available_copies, members_count=members_count,
                    active_loans=active_loans, overdue_count=overdue_count, recent_rows=recent_rows)
    finally:
        db.close()

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse("/", status_code=303)
    return page(request, "login.html", error=None)

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session.clear()
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)
    return page(request, "login.html", error="Incorrect username or password.")

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/books", response_class=HTMLResponse)
def books_page(request: Request, q: str = ""):
    require_login(request)
    db = db_session()
    try:
        query = db.query(Book)
        if q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(or_(Book.title.ilike(term), Book.author.ilike(term), Book.isbn.ilike(term), Book.category.ilike(term)))
        books = query.order_by(Book.title.asc()).all()
        return page(request, "books.html", books=books, q=q, message=request.query_params.get("message"))
    finally:
        db.close()

@app.post("/books/add")
def add_book(request: Request, title: str = Form(...), author: str = Form(...),
             isbn: str = Form(""), category: str = Form("General"), total_copies: int = Form(...)):
    require_login(request)
    if total_copies < 1:
        return RedirectResponse("/books?message=" + quote("Copies must be at least 1."), status_code=303)
    db = db_session()
    try:
        clean_isbn = isbn.strip() or None
        if clean_isbn and db.query(Book).filter(Book.isbn == clean_isbn).first():
            return RedirectResponse("/books?message=" + quote("That ISBN already exists."), status_code=303)
        book = Book(title=title.strip(), author=author.strip(), isbn=clean_isbn,
                    category=category.strip() or "General", total_copies=total_copies, available_copies=total_copies)
        db.add(book)
        db.commit()
        return RedirectResponse("/books?message=" + quote("Book added successfully."), status_code=303)
    finally:
        db.close()

@app.post("/books/{book_id}/delete")
def delete_book(request: Request, book_id: int):
    require_login(request)
    db = db_session()
    try:
        book = db.get(Book, book_id)
        if not book:
            return RedirectResponse("/books?message=" + quote("Book not found."), status_code=303)
        if db.query(Loan).filter(Loan.book_id == book_id, Loan.returned_on.is_(None)).first():
            return RedirectResponse("/books?message=" + quote("Cannot delete a book while copies are issued."), status_code=303)
        db.query(Loan).filter(Loan.book_id == book_id).delete()
        db.delete(book)
        db.commit()
        return RedirectResponse("/books?message=" + quote("Book deleted."), status_code=303)
    finally:
        db.close()

@app.get("/members", response_class=HTMLResponse)
def members_page(request: Request, q: str = ""):
    require_login(request)
    db = db_session()
    try:
        query = db.query(Member)
        if q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(or_(Member.name.ilike(term), Member.email.ilike(term), Member.phone.ilike(term)))
        members = query.order_by(Member.name.asc()).all()
        return page(request, "members.html", members=members, q=q, message=request.query_params.get("message"))
    finally:
        db.close()

@app.post("/members/add")
def add_member(request: Request, name: str = Form(...), email: str = Form(...), phone: str = Form("")):
    require_login(request)
    db = db_session()
    try:
        clean_email = email.strip().lower()
        if db.query(Member).filter(Member.email == clean_email).first():
            return RedirectResponse("/members?message=" + quote("A member with this email already exists."), status_code=303)
        db.add(Member(name=name.strip(), email=clean_email, phone=phone.strip()))
        db.commit()
        return RedirectResponse("/members?message=" + quote("Member added successfully."), status_code=303)
    finally:
        db.close()

@app.post("/members/{member_id}/delete")
def delete_member(request: Request, member_id: int):
    require_login(request)
    db = db_session()
    try:
        member = db.get(Member, member_id)
        if not member:
            return RedirectResponse("/members?message=" + quote("Member not found."), status_code=303)
        if db.query(Loan).filter(Loan.member_id == member_id, Loan.returned_on.is_(None)).first():
            return RedirectResponse("/members?message=" + quote("Return all borrowed books before deleting this member."), status_code=303)
        db.query(Loan).filter(Loan.member_id == member_id).delete()
        db.delete(member)
        db.commit()
        return RedirectResponse("/members?message=" + quote("Member deleted."), status_code=303)
    finally:
        db.close()

@app.get("/loans", response_class=HTMLResponse)
def loans_page(request: Request, status: str = "active"):
    require_login(request)
    db = db_session()
    try:
        query = db.query(Loan)
        if status == "active":
            query = query.filter(Loan.returned_on.is_(None))
        elif status == "returned":
            query = query.filter(Loan.returned_on.is_not(None))
        loans = query.order_by(Loan.issued_on.desc(), Loan.id.desc()).all()
        rows = []
        for loan in loans:
            book, member = db.get(Book, loan.book_id), db.get(Member, loan.member_id)
            if book and member:
                rows.append({"loan": loan, "book": book, "member": member,
                             "overdue": loan.returned_on is None and loan.due_on < date.today()})
        books = db.query(Book).filter(Book.available_copies > 0).order_by(Book.title.asc()).all()
        members = db.query(Member).order_by(Member.name.asc()).all()
        return page(request, "loans.html", rows=rows, books=books, members=members, status=status,
                    message=request.query_params.get("message"), today=date.today())
    finally:
        db.close()

@app.post("/loans/issue")
def issue_book(request: Request, book_id: int = Form(...), member_id: int = Form(...), due_on: date = Form(...)):
    require_login(request)
    if due_on < date.today():
        return RedirectResponse("/loans?message=" + quote("Due date cannot be in the past."), status_code=303)
    db = db_session()
    try:
        book, member = db.get(Book, book_id), db.get(Member, member_id)
        if not book or not member:
            return RedirectResponse("/loans?message=" + quote("Select a valid book and member."), status_code=303)
        if book.available_copies < 1:
            return RedirectResponse("/loans?message=" + quote("No copies of that book are available."), status_code=303)
        book.available_copies -= 1
        db.add(Loan(book_id=book_id, member_id=member_id, due_on=due_on))
        db.commit()
        return RedirectResponse("/loans?message=" + quote("Book issued successfully."), status_code=303)
    finally:
        db.close()

@app.post("/loans/{loan_id}/return")
def return_book(request: Request, loan_id: int):
    require_login(request)
    db = db_session()
    try:
        loan = db.get(Loan, loan_id)
        if not loan or loan.returned_on:
            return RedirectResponse("/loans?message=" + quote("This loan is already returned or does not exist."), status_code=303)
        loan.returned_on = date.today()
        book = db.get(Book, loan.book_id)
        if book:
            book.available_copies = min(book.total_copies, book.available_copies + 1)
        db.commit()
        return RedirectResponse("/loans?message=" + quote("Book returned successfully."), status_code=303)
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}
