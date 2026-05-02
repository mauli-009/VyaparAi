import os
from fastapi import FastAPI
from app.routes.upload import router as upload_router
from app.routes.mapping import router as mapping_router
from app.routes.query import router as query_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

allowed_origins = [
    frontend_url,
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",  # ✅ allows all vercel preview URLs
)

app.include_router(upload_router)
app.include_router(mapping_router)
app.include_router(query_router)

@app.get("/")
def root():
    return {"message": "Backend is running 🚀"}