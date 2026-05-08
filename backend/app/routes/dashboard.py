from fastapi import APIRouter, HTTPException, Header
from app.db.database import dashboards_collection

router = APIRouter()

@router.get("/dashboards/{file_id}")
def get_dashboard(file_id: str):
    dashboard = dashboards_collection.find_one({"file_id": file_id})
    
    if not dashboard:
        # Return an empty layout so the frontend doesn't crash
        return {"layout": []}
        
    # Remove the MongoDB _id before sending to frontend
    dashboard.pop("_id", None)
    return dashboard

#this is dashboard route