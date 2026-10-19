import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from database import init_db, get_connection
from schemas import ProductListResponse, HealthResponse
from models import query_products, get_all_categories, InvalidCursorError, InvalidFilterError

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("product_catalog")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager ensuring database is initialized upon startup."""
    logger.info("Initializing product catalog database...")
    init_db()
    yield
    logger.info("Application shutdown complete.")

app = FastAPI(
    title="Product Catalog REST API",
    description="High-performance product catalog with search, multi-field filtering, keyset pagination, and sorting.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local cross-origin development if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers for clean error envelopes
@app.exception_handler(InvalidCursorError)
async def invalid_cursor_handler(request: Request, exc: InvalidCursorError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "error": "InvalidCursor"},
    )

@app.exception_handler(InvalidFilterError)
async def invalid_filter_handler(request: Request, exc: InvalidFilterError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "error": "InvalidFilter"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Flatten validation errors for friendly client consumption
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "; ".join(errors), "error": "ValidationError"},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception encountered on %s", request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error": "InternalServerError"},
    )

# Static directory setup
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the single-page application frontend."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Product Catalog API is running. Explore API documentation at /docs"}

@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check endpoint",
    description="Check API status and database connectivity."
)
async def get_health():
    """Verify system health and total product count."""
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM products;")
            row = cursor.fetchone()
            total = row["total"] if row else 0
            return HealthResponse(
                status="healthy",
                database="connected",
                totalProducts=total
            )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connectivity failure")

@app.get(
    "/api/categories",
    response_model=List[str],
    tags=["Products"],
    summary="List product categories",
    description="Retrieve all unique product categories currently available."
)
async def list_categories():
    """Retrieve distinct product categories."""
    conn = get_connection()
    try:
        return get_all_categories(conn)
    finally:
        conn.close()

@app.get(
    "/api/products",
    response_model=ProductListResponse,
    tags=["Products"],
    summary="Search, filter, sort, and paginate products",
    description="Perform high-performance keyset pagination with multi-field filtering and full-text substring search."
)
async def get_products(
    search: Optional[str] = Query(None, description="Case-insensitive substring search across name and description"),
    category: Optional[str] = Query(None, description="Exact category match"),
    priceMin: Optional[float] = Query(None, description="Minimum price, inclusive"),
    priceMax: Optional[float] = Query(None, description="Maximum price, inclusive"),
    inStock: Optional[bool] = Query(None, description="Filter by stock availability: true (stock > 0) or false (stock == 0)"),
    sort: str = Query("createdAt", description="Sortable column: id, name, description, category, price, stock, rating, createdAt"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(20, ge=1, le=100, description="Page size (1 to 100, default 20)"),
    cursor: Optional[str] = Query(None, description="Opaque base64 keyset pagination cursor"),
):
    """Query products catalog with full cursor pagination and multi-parameter filtering."""
    conn = get_connection()
    try:
        return query_products(
            conn=conn,
            search=search,
            category=category,
            price_min=priceMin,
            price_max=priceMax,
            in_stock=inStock,
            sort=sort,
            order=order,
            limit=limit,
            cursor=cursor,
        )
    finally:
        conn.close()
