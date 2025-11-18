from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi_pagination import add_pagination
from fastapi.security import OAuth2PasswordRequestForm

from db.models import User
from db.users import get_by_username
from routers import items, users


app = FastAPI()
add_pagination(app)


app.include_router(items.router)
app.include_router(users.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the main API!"}


@app.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> dict[str, str]:
    user: User = get_by_username(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not form_data.password == user.password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user.username, "token_type": "bearer"}
