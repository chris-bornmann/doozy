from fastapi import FastAPI
from fastapi_pagination import add_pagination
from routers import items, users


app = FastAPI()
add_pagination(app)


app.include_router(items.router)
app.include_router(users.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the main API!"}
