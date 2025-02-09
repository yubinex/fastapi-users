from fastapi import FastAPI
from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import Optional
from contextlib import asynccontextmanager

engine = create_engine("sqlite:///users.db")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
    print("shutdown")


app = FastAPI(lifespan=lifespan)


class UserModel(SQLModel):
    firstname: str
    lastname: str
    email: EmailStr
    password: str
    age: int


class UserTable(UserModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


@app.post("/register", status_code=201)
async def create_user(user: UserModel):
    new_user = UserTable.model_validate(user)
    with Session(engine) as session:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {"id": new_user.id, "message": "user registered successfully"}


@app.get("/users", status_code=200)
async def get_users():
    statement = select(UserTable)
    with Session(engine) as session:
        users = session.exec(statement).all()
        return users
