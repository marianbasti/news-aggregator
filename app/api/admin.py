from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging
from app.services.article_service import update_related_articles_for_existing

logger = logging.getLogger(__name__)
router = APIRouter()

# Set up templates directory, assuming it's in app/templates
# Correct path from app/api/admin.py to app/templates
templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

@router.get("/", response_class=HTMLResponse, summary="Admin control panel")
async def get_admin_panel(request: Request):
    """
    Serves the main admin control panel page.
    """
    try:
        # You can pass initial data to the template if needed
        # For example, current status of services, recent activities, etc.
        return templates.TemplateResponse("admin.html", {"request": request, "title": "Admin Panel"})
    except Exception as e:
        logger.error(f"Error rendering admin panel: {e}", exc_info=True)
        # Fallback or error page
        return HTMLResponse(content=f"<h1>Error rendering admin panel</h1><p>{str(e)}</p>", status_code=500)

# Admin endpoints are defined below

@router.post("/update-related-articles", summary="Update related articles for existing articles (Admin)")
async def update_related_articles_admin(limit: int = 100, days_back: int = 30):
    """
    Admin action to update related articles for existing articles.
    This is useful for a one-time run when the related_article_ids feature is first introduced.

    Args:
        limit: Maximum number of articles to process
        days_back: Only process articles from the last X days
    """
    logger.info(f"Admin action: Updating related articles for existing articles (limit={limit}, days_back={days_back}).")
    try:
        result = await update_related_articles_for_existing(limit=limit, days_back=days_back)
        return {
            "message": f"Updated related articles. Processed: {result['processed']}, Linked: {result['linked']} articles.",
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error updating related articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating related articles: {str(e)}")

# Add more admin-specific API endpoints here if needed.
# For example, endpoints to get specific logs, manage users (if any), etc.
