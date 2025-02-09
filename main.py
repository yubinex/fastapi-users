import datetime
from contextlib import asynccontextmanager
from typing import Optional

import bcrypt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt
from pydantic import EmailStr, ValidationInfo, field_validator
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select

engine = create_engine("sqlite:///users.db")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
    print("shutdown")


app = FastAPI(lifespan=lifespan)

oauth2_schema = OAuth2PasswordBearer(tokenUrl="login")

# in a real app this should be in an .env file
SECRET_KEY = "very-secret-key"


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
    user.password = str(bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()))
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

    jwt_data = {
        "email": db_user.email,
        "exp": datetime.datetime.now() + datetime.timedelta(minutes=30),
    }
    access_token = jwt.encode(claims=jwt_data, key=SECRET_KEY, algorithm="HS256")

    return {"access_token": access_token, "token_type": "bearer"}


# if no values from the token are needed, the dependency can be set directly in the
# decorator - this way, there's no unused variable
@app.get("/users", status_code=200, dependencies=[Depends(oauth2_schema)])
async def get_users(session: Session = Depends(get_session)):
    statement = select(UserTable)
    users = session.exec(statement).all()
    return users


# if we need values stored in the token, we add the dependency in the function
# as a parameter to get access to the token as a variable
@app.get("/current_user")
async def get_current_user(
    session: Session = Depends(get_session), token: str = Depends(oauth2_schema)
):
    payload = jwt.decode(token=token, key=SECRET_KEY)
    email = payload.get("email")
    current_user = session.exec(
        select(UserTable).where(UserTable.email == email)
    ).first()
    return current_user
