import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Set temporary isolated test database before importing app
temp_dir = tempfile.mkdtemp()
test_db_path = os.path.join(temp_dir, "test_products.db")
os.environ["DATABASE_PATH"] = test_db_path

from database import init_db, get_db_context
from main import app
from seed import seed_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup an isolated SQLite test database with dedicated known test records."""
    init_db(test_db_path)
    
    with get_db_context(test_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products;")
        
        # Insert 60 known test products with controlled values
        test_data = []
        categories = ["Electronics", "Home & Kitchen", "Fashion", "Sports", "Books", "Beauty"]
        
        for i in range(1, 61):
            category = categories[(i - 1) % len(categories)]
            # Introduce intentional duplicate prices to test tie-breaker sorting
            price = 100.0 if i in (5, 6, 7, 8) else round(20.0 + (i * 15.0), 2)
            # Introduce out-of-stock items for i divisible by 5
            stock = 0 if (i % 5 == 0) else (i * 4)
            rating = round(1.0 + ((i % 5) * 0.8), 1)
            created_at = f"2026-01-{i:02d}T10:00:00Z" if i <= 31 else f"2026-02-{(i-31):02d}T10:00:00Z"
            
            name = f"TestProduct {i}"
            desc = f"Description for product {i} with high efficiency."
            if i == 1:
                name = "Ultra Wireless Noise-Cancelling Headphones"
                desc = "Flagship audio experience with bluetooth 5.3"
            elif i == 2:
                name = "Classic Coffee Maker"
                desc = "Compact wireless charging pad included in bundle"
            elif i == 10:
                name = "Mechanical Gaming Keyboard"
                desc = "Full RGB backlight wireless switch"

            test_data.append((name, desc, category, price, stock, rating, created_at))

        cursor.executemany("""
            INSERT INTO products (name, description, category, price, stock, rating, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, test_data)

    yield test_db_path

    # Clean up test database file
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

# 1. Health endpoint
def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["totalProducts"] == 60

# 2. Categories endpoint
def test_categories_endpoint(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    cats = response.json()
    assert isinstance(cats, list)
    assert len(cats) == 6
    assert "Electronics" in cats
    assert "Home & Kitchen" in cats
    assert cats == sorted(cats)

# 3. Search across product names
def test_search_across_product_names(client):
    response = client.get("/api/products?search=Headphones")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] >= 1
    assert any("Headphones" in p["name"] for p in payload["data"])

# 4. Search across descriptions
def test_search_across_descriptions(client):
    # 'bluetooth' only appears in the description of product 1
    response = client.get("/api/products?search=bluetooth")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] >= 1
    assert any("bluetooth" in p["description"].lower() for p in payload["data"])

# 5. Category filtering
def test_category_filtering(client):
    response = client.get("/api/products?category=Electronics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] == 10
    assert all(p["category"] == "Electronics" for p in payload["data"])

# 6. Minimum and maximum price filtering
def test_price_filtering(client):
    response = client.get("/api/products?priceMin=50&priceMax=200")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] > 0
    assert all(50 <= p["price"] <= 200 for p in payload["data"])

# 7. In-stock and out-of-stock filtering
def test_stock_filtering(client):
    # In stock
    res_in = client.get("/api/products?inStock=true")
    assert res_in.status_code == 200
    data_in = res_in.json()
    assert all(p["stock"] > 0 for p in data_in["data"])

    # Out of stock
    res_out = client.get("/api/products?inStock=false")
    assert res_out.status_code == 200
    data_out = res_out.json()
    assert data_out["meta"]["total"] == 12  # 60 / 5 = 12
    assert all(p["stock"] == 0 for p in data_out["data"])

# 8. Multiple filters combined
def test_multiple_filters_combined(client):
    response = client.get("/api/products?category=Electronics&inStock=true&priceMin=10&priceMax=500")
    assert response.status_code == 200
    payload = response.json()
    for p in payload["data"]:
        assert p["category"] == "Electronics"
        assert p["stock"] > 0
        assert 10 <= p["price"] <= 500

# 9. Ascending and descending sorting
def test_sorting_asc_and_desc(client):
    # Price ASC
    res_asc = client.get("/api/products?sort=price&order=asc&limit=50")
    assert res_asc.status_code == 200
    prices_asc = [p["price"] for p in res_asc.json()["data"]]
    assert prices_asc == sorted(prices_asc)

    # Price DESC
    res_desc = client.get("/api/products?sort=price&order=desc&limit=50")
    assert res_desc.status_code == 200
    prices_desc = [p["price"] for p in res_desc.json()["data"]]
    assert prices_desc == sorted(prices_desc, reverse=True)

# 10. Every supported sortable field
@pytest.mark.parametrize("sort_field", [
    "id", "name", "description", "category", "price", "stock", "rating", "createdAt"
])
def test_all_sortable_fields(client, sort_field):
    res_asc = client.get(f"/api/products?sort={sort_field}&order=asc&limit=10")
    assert res_asc.status_code == 200
    res_desc = client.get(f"/api/products?sort={sort_field}&order=desc&limit=10")
    assert res_desc.status_code == 200

# 11. First-page pagination
def test_first_page_pagination(client):
    res = client.get("/api/products?limit=15")
    assert res.status_code == 200
    body = res.json()
    assert len(body["data"]) == 15
    assert body["meta"]["prevCursor"] is None
    assert body["meta"]["nextCursor"] is not None

# 12. Next-page pagination
def test_next_page_pagination(client):
    # Fetch page 1
    page1 = client.get("/api/products?sort=id&order=asc&limit=10").json()
    next_cursor = page1["meta"]["nextCursor"]
    assert next_cursor is not None

    # Fetch page 2
    page2 = client.get(f"/api/products?sort=id&order=asc&limit=10&cursor={next_cursor}").json()
    assert len(page2["data"]) == 10
    
    # Assert IDs on page 2 are strictly greater than page 1 IDs
    p1_ids = [p["id"] for p in page1["data"]]
    p2_ids = [p["id"] for p in page2["data"]]
    assert max(p1_ids) < min(p2_ids)

# 13. Previous-page pagination
def test_previous_page_pagination(client):
    # Fetch page 1
    page1 = client.get("/api/products?sort=id&order=asc&limit=10").json()
    next_cursor = page1["meta"]["nextCursor"]

    # Fetch page 2
    page2 = client.get(f"/api/products?sort=id&order=asc&limit=10&cursor={next_cursor}").json()
    prev_cursor = page2["meta"]["prevCursor"]
    assert prev_cursor is not None

    # Navigate back to page 1 using prevCursor
    page1_back = client.get(f"/api/products?sort=id&order=asc&limit=10&cursor={prev_cursor}").json()
    p1_ids = [p["id"] for p in page1["data"]]
    p1_back_ids = [p["id"] for p in page1_back["data"]]
    assert p1_ids == p1_back_ids
    assert page1_back["meta"]["prevCursor"] is None

# 14. Duplicate sort values at page boundaries
def test_duplicate_sort_values_at_page_boundary(client):
    # Products 5, 6, 7, 8 all have price = 100.0
    # Query with limit = 6, sort by price asc
    res1 = client.get("/api/products?sort=price&order=asc&limit=6").json()
    next_cursor = res1["meta"]["nextCursor"]
    assert next_cursor is not None

    res2 = client.get(f"/api/products?sort=price&order=asc&limit=6&cursor={next_cursor}").json()
    
    ids_page1 = [p["id"] for p in res1["data"]]
    ids_page2 = [p["data"] if isinstance(p, dict) and "id" not in p else p["id"] for p in res2["data"]]

    # Ensure zero overlap and continuous traversal even when prices are identical
    intersection = set(ids_page1).intersection(set(ids_page2))
    assert len(intersection) == 0

# 15. Invalid cursors
def test_invalid_cursors(client):
    # Random junk
    res1 = client.get("/api/products?cursor=invalid_garbage_token")
    assert res1.status_code == 400
    assert "InvalidCursor" in res1.json()["error"]

    # Corrupt base64
    res2 = client.get("/api/products?cursor=%%%notbase64")
    assert res2.status_code == 400

    # Incompatible cursor: cursor encoded for name asc, but query requests price desc
    from models import encode_cursor
    incompatible_cursor = encode_cursor("SomeName", 1, "next", "name", "asc")
    res3 = client.get(f"/api/products?sort=price&order=desc&cursor={incompatible_cursor}")
    assert res3.status_code == 400
    assert "does not match requested sort" in res3.json()["detail"]

# 16. Invalid sorting parameters
def test_invalid_sorting_parameters(client):
    res = client.get("/api/products?sort=drop_table")
    assert res.status_code == 400

    res_order = client.get("/api/products?sort=price&order=sideways")
    assert res_order.status_code == 400

# 17. Invalid page sizes
def test_invalid_page_sizes(client):
    res_zero = client.get("/api/products?limit=0")
    assert res_zero.status_code == 400

    res_too_big = client.get("/api/products?limit=250")
    assert res_too_big.status_code == 400

# 18. Invalid price ranges
def test_invalid_price_ranges(client):
    # priceMin > priceMax
    res_inverted = client.get("/api/products?priceMin=500&priceMax=200")
    assert res_inverted.status_code == 400
    assert "priceMin" in res_inverted.json()["detail"]

    # negative price
    res_neg = client.get("/api/products?priceMin=-10")
    assert res_neg.status_code == 400

# 19. Empty search results
def test_empty_search_results(client):
    res = client.get("/api/products?search=NonExistentKeywordXYZ98765")
    assert res.status_code == 200
    body = res.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["nextCursor"] is None
    assert body["meta"]["prevCursor"] is None

# 20. Accurate total counts and response metadata
def test_accurate_total_counts_and_response_metadata(client):
    res = client.get("/api/products?category=Books&limit=5")
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 10
    assert body["meta"]["appliedFilters"]["category"] == "Books"
    assert body["meta"]["appliedFilters"]["limit"] == 5
    assert len(body["data"]) == 5

# Full pagination traversal test: detects missing or duplicate records across all pages
def test_full_pagination_no_duplicates_no_missing(client):
    """Paginate through all 60 items with page size 13 and ensure all 60 distinct items are retrieved."""
    visited_ids = []
    cursor = None
    page_count = 0
    
    while True:
        url = "/api/products?sort=id&order=asc&limit=13"
        if cursor:
            url += f"&cursor={cursor}"
        res = client.get(url)
        assert res.status_code == 200
        payload = res.json()
        items = payload["data"]
        
        for item in items:
            visited_ids.append(item["id"])
            
        cursor = payload["meta"]["nextCursor"]
        page_count += 1
        if not cursor:
            break

    assert len(visited_ids) == 60
    assert len(set(visited_ids)) == 60
    assert page_count == 5  # ceil(60 / 13) = 5
