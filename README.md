# Production-Quality Product Catalog REST API (Challenge 3)

A high-performance, production-ready Product Catalog REST API and interactive dashboard built with **Python**, **FastAPI**, **SQLite**, and **vanilla HTML5/CSS3/JavaScript**.

Featuring **true keyset/cursor-based pagination** (zero `OFFSET`), full-text substring search across multiple fields, multi-field filtering, parameterized SQL queries with column allowlists, and bidirectional browser **URL query string state synchronization**.

---

## Architecture & Features

- **True Keyset / Cursor Pagination**: No `OFFSET` scanning. Encodes opaque, base64url JSON tokens containing boundary values, primary key tie-breakers, sort field, direction, and order. Handles duplicate sort values and bidirectional (`next`/`prev`) navigation seamlessly.
- **Search**: Case-insensitive substring search across `name` and `description` with debounced input in the UI.
- **Multi-Field Filtering**:
  - Exact category matching
  - Minimum price (`priceMin`, inclusive)
  - Maximum price (`priceMax`, inclusive)
  - Stock availability (`inStock=true` or `inStock=false`)
  - Full filter combination support with input validation (returns HTTP 400 on inverted ranges or negative prices).
- **Configurable Sorting**: Supports all 8 product fields (`id`, `name`, `description`, `category`, `price`, `stock`, `rating`, `createdAt`) in `asc` or `desc` order with SQL injection prevention via column allowlists.
- **Strict Response Envelope**: Standardized structure matching `{"data": [...], "meta": {"total": N, "nextCursor": "...", "prevCursor": "...", "appliedFilters": {...}}}`.
- **Production Dashboard UI**: Modern dark theme with Google Fonts (Outfit, Inter, JetBrains Mono), micro-animations, category chips, stock badges, star ratings, and Indian Rupee (`₹`) currency formatting.
- **Bidirectional URL State Sync**: All filters, search keywords, sorting headers, page size, and pagination cursors persist in `window.location.search` with `URLSearchParams` and `popstate` browser navigation support.
- **Database Indexing**: Optimized SQLite indexes on `category`, `price`, `stock`, `rating`, `createdAt`, `name`, and composite `(category, price)`.

---

## Directory Structure

```text
IRIS/
├── main.py              # FastAPI application, exception handlers, static routes
├── database.py          # SQLite connection manager, WAL mode, schema & indexes
├── models.py            # Keyset pagination engine, query builder, cursor validation
├── schemas.py           # Pydantic schemas and response envelopes
├── seed.py              # Reproducible Faker seed script (700 products)
├── requirements.txt     # Python dependencies
├── README.md            # Complete documentation and setup guide
├── products.db          # SQLite database with 700 seeded products
├── static/
│   ├── index.html       # Semantic dashboard markup and controls
│   ├── styles.css       # Design system, glassmorphism, responsive table
│   └── app.js           # Pure vanilla JS engine with URLSearchParams sync
└── tests/
    ├── __init__.py
    └── test_products.py # 28 comprehensive pytest unit and integration tests
```

---

## System Requirements

- **Operating System**: Windows 10/11 (or Linux/macOS)
- **Python**: Python 3.10, 3.11, 3.12, or 3.13 (Tested on Python 3.13)
- **PowerShell**: Windows PowerShell 5.1 or PowerShell 7+

---

## Quickstart (Windows PowerShell)

### 1. Clone or Open Workspace Directory

```powershell
cd c:\Users\PRASAD\OneDrive\Attachments\Desktop\IRIS
```

### 2. (Optional) Create & Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Initialize Database and Seed Data

Generate 700 realistic, category-diverse products using Faker:

```powershell
python seed.py --reset
```

> **Note**: Running `python seed.py` without `--reset` is idempotent—it checks existing counts and avoids creating duplicate records.

### 5. Start the Server

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Application URLs

| Service | URL |
| :--- | :--- |
| **Interactive Web Dashboard** | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) |
| **Interactive Swagger UI Docs** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| **ReDoc Alternative API Docs** | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |
| **Health Check Endpoint** | [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) |
| **Categories Endpoint** | [http://127.0.0.1:8000/api/categories](http://127.0.0.1:8000/api/categories) |

---

## Running Automated Tests

The test suite runs against an **isolated temporary SQLite database**, leaving your seeded `products.db` completely intact:

```powershell
pytest -v
```

### Test Coverage Highlights (28/28 Passing):
1. `test_health_endpoint`: Checks status and total records.
2. `test_categories_endpoint`: Validates distinct, sorted category output.
3. `test_search_across_product_names`: Tests case-insensitive name matching.
4. `test_search_across_descriptions`: Tests substring matching in descriptions.
5. `test_category_filtering`: Verifies single and multiple category queries.
6. `test_price_filtering`: Verifies min and max price ranges.
7. `test_stock_filtering`: Verifies `inStock=true` (> 0) and `inStock=false` (== 0).
8. `test_multiple_filters_combined`: Combines category, price range, and stock availability.
9. `test_sorting_asc_and_desc`: Tests ordering direction on numeric/date fields.
10. `test_all_sortable_fields`: Parameterized test across all 8 fields.
11. `test_first_page_pagination`: Verifies initial page state and cursor generation.
12. `test_next_page_pagination`: Validates forward keyset navigation.
13. `test_previous_page_pagination`: Validates backward navigation to exact prior records.
14. `test_duplicate_sort_values_at_page_boundary`: Ensures tie-breaking by `id` does not duplicate or skip items with identical prices.
15. `test_invalid_cursors`: Validates 400 Bad Request on garbage, corrupt base64, or mismatched sort fields.
16. `test_invalid_sorting_parameters`: Validates 400 Bad Request on SQL injection attempts.
17. `test_invalid_page_sizes`: Tests limit boundaries (must be between 1 and 100).
18. `test_invalid_price_ranges`: Verifies 400 Bad Request when `priceMin > priceMax` or `priceMin < 0`.
19. `test_empty_search_results`: Confirms clean metadata and empty `data` array.
20. `test_accurate_total_counts_and_response_metadata`: Verifies count reflects filter results before pagination.
21. `test_full_pagination_no_duplicates_no_missing`: Traverses all records page by page, asserting 0 duplicate and 0 missing items.

---

## API Reference & Examples

### 1. Basic Product Query

```http
GET /api/products?limit=20
```

### 2. Search & Multi-Field Filter Query

```http
GET /api/products?search=wireless&category=Electronics&priceMin=1000&priceMax=50000&inStock=true&sort=price&order=asc&limit=10
```

### 3. Keyset Pagination Forward Query

```http
GET /api/products?sort=price&order=asc&limit=10&cursor=eyJ2IjoxMDAuMCwiaSI6NiwicCI6Im5leHQiLCJzIjoicHJpY2UiLCJvIjoiYXNjIn0=
```

### Standard Response Envelope

```json
{
  "data": [
    {
      "id": 14,
      "name": "Wireless Noise-Cancelling Headphones Pro",
      "description": "High fidelity audio with 40-hour battery life.",
      "category": "Electronics",
      "price": 14999.00,
      "stock": 42,
      "rating": 4.8,
      "createdAt": "2026-08-12T14:32:00Z"
    }
  ],
  "meta": {
    "total": 650,
    "nextCursor": "eyJ2IjoxNDk5OS4wLCJpIjoxNCwiZCI6Im5leHQiLCJzIjoicHJpY2UiLCJvIjoiYXNjIn0=",
    "prevCursor": null,
    "appliedFilters": {
      "search": "wireless",
      "category": "Electronics",
      "priceMin": 1000.0,
      "priceMax": 50000.0,
      "inStock": true,
      "sort": "price",
      "order": "asc",
      "limit": 10
    }
  }
}
```

---

## How Cursor-Based (Keyset) Pagination Works

Instead of slow and drift-prone `OFFSET N`, the engine queries relative to the boundary of the current page using a composite tuple `(SortField, ID)`:

- **Next Page (Ascending)**:
  ```sql
  WHERE (SortField > :cur_val OR (SortField = :cur_val AND id > :cur_id))
  ORDER BY SortField ASC, id ASC
  LIMIT :limit + 1
  ```
- **Previous Page (Ascending)**:
  ```sql
  WHERE (SortField < :cur_val OR (SortField = :cur_val AND id < :cur_id))
  ORDER BY SortField DESC, id DESC
  LIMIT :limit + 1
  ```
  *(Results are reversed in application memory back to standard order).*

- **Next Page (Descending)**:
  ```sql
  WHERE (SortField < :cur_val OR (SortField = :cur_val AND id < :cur_id))
  ORDER BY SortField DESC, id DESC
  LIMIT :limit + 1
  ```

- **Tie-Breaker**: The `id` primary key uniquely breaks ties whenever multiple rows share identical sort values (e.g. products with identical prices or dates).
- **No Stale Drift**: Inserting or deleting records does not offset the reader's view.

---

## Limitations & Production Recommendations

1. **SQLite Substring Search vs. FTS5**:
   - Current implementation uses parameterized `LIKE %search%` across `name` and `description`, which performs case-insensitive substring matching.
   - For catalogs exceeding 100,000+ items, SQLite **FTS5** (Full-Text Search 5) virtual tables with BM25 ranking should be utilized for sub-millisecond prefix, phonetic, and tokenized searches.
2. **Reverse Navigation Boundary**:
   - When reaching the start or end of the catalog, cursors return `null`, allowing UI navigation buttons to disable predictably.
