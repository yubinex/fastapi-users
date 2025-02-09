from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr, field_validator, ValidationInfo
from sqlmodel import SQLModel, Field, Session, create_engine, select, UniqueConstraint
from typing import Optional
from contextlib import asynccontextmanager
import bcrypt

engine = create_engine("sqlite:///users.db")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
    print("shutdown")


app = FastAPI(lifespan=lifespan)


class UserBase(SQLModel):
    firstname: str
    lastname: str
    username: str
    email: EmailStr
    password: str
    age: int


class UserCreate(UserBase):
    repeat_password: str

    @field_validator("repeat_password")
    def passwords_must_match(cls, v: str, info: ValidationInfo) -> str:
        if v != info.data.get("password"):
            raise ValueError("passwords must match")
        return v


class UserTable(UserBase, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email"), UniqueConstraint("username"))

    id: Optional[int] = Field(default=None, primary_key=True)


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/register", status_code=201)
async def create_user(user: UserCreate, session: Session = Depends(get_session)):
    user.password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
    new_user = UserTable.model_validate(user)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"id": new_user.id, "message": "user registered successfully"}


@app.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    db_user = session.exec(
        select(UserTable).where(UserTable.username == form_data.username)
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="incorrect username or password")

    if not bcrypt.checkpw(
        form_data.password.encode("utf-8"), db_user.password.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="incorrect username or password")

    return {"user": f"logged in as {db_user.username}"}


@app.get("/users", status_code=200)
async def get_users(session: Session = Depends(get_session)):
    statement = select(UserTable)
    users = session.exec(statement).all()
    return users
