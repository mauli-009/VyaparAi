from fastapi import FastAPI
from app.routes.upload import router as upload_router
from app.routes.mapping import router as mapping_router
from app.routes.query import router as query_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.include_router(upload_router)
app.include_router(mapping_router)
app.include_router(query_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}