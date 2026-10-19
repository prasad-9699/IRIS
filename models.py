import base64
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from schemas import Product, AppliedFilters, ProductMeta, ProductListResponse

SORTABLE_FIELDS = {
    "id": "id",
    "name": "name",
    "description": "description",
    "category": "category",
    "price": "price",
    "stock": "stock",
    "rating": "rating",
    "createdAt": "createdAt",
}

class InvalidCursorError(ValueError):
    """Raised when a pagination cursor is malformed or incompatible."""
    pass

class InvalidFilterError(ValueError):
    """Raised when filter parameters are invalid."""
    pass

def encode_cursor(val: Any, item_id: int, direction: str, sort_field: str, order: str) -> str:
    """
    Encode pagination state into an opaque base64 string.
    Payload contains:
      - v: sort column value of boundary item
      - i: tie-breaker id of boundary item
      - d: navigation direction ('next' or 'prev')
      - s: sort field name
      - o: sort order ('asc' or 'desc')
    """
    payload = {
        "v": val,
        "i": item_id,
        "d": direction,
        "s": sort_field,
        "o": order,
    }
    json_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")

def decode_cursor(cursor_str: str, expected_sort: str, expected_order: str) -> Dict[str, Any]:
    """
    Decode and validate an opaque cursor string.
    Ensures cursor integrity and compatibility with active sort parameters.
    """
    if not cursor_str:
        raise InvalidCursorError("Empty cursor provided.")
    try:
        # Re-add padding if needed
        rem = len(cursor_str) % 4
        if rem > 0:
            cursor_str += "=" * (4 - rem)
        decoded_bytes = base64.urlsafe_b64decode(cursor_str.encode("ascii"))
        payload = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        raise InvalidCursorError(f"Malformed or non-decodable cursor: {str(e)}")

    if not isinstance(payload, dict):
        raise InvalidCursorError("Cursor payload is not a valid JSON object.")

    for key in ("v", "i", "d", "s", "o"):
        if key not in payload:
            raise InvalidCursorError(f"Cursor payload missing required key '{key}'.")

    if payload["d"] not in ("next", "prev"):
        raise InvalidCursorError(f"Invalid cursor direction: '{payload['d']}'.")

    if payload["s"] != expected_sort:
        raise InvalidCursorError(
            f"Cursor sort field '{payload['s']}' does not match requested sort '{expected_sort}'."
        )

    if payload["o"].lower() != expected_order.lower():
        raise InvalidCursorError(
            f"Cursor sort order '{payload['o']}' does not match requested order '{expected_order}'."
        )

    try:
        payload["i"] = int(payload["i"])
    except (ValueError, TypeError):
        raise InvalidCursorError("Cursor tie-breaker id must be an integer.")

    return payload

def get_all_categories(conn: sqlite3.Connection) -> List[str]:
    """Retrieve distinct product categories in alphabetical order."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM products ORDER BY category ASC;")
    rows = cursor.fetchall()
    return [row["category"] for row in rows if row["category"]]

def query_products(
    conn: sqlite3.Connection,
    search: Optional[str] = None,
    category: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock: Optional[bool] = None,
    sort: str = "createdAt",
    order: str = "desc",
    limit: int = 20,
    cursor: Optional[str] = None,
) -> ProductListResponse:
    """
    Execute keyset/cursor-based pagination query on products table with multi-field filtering.
    Guarantees no OFFSET usage, stable ordering with tie-breakers, and validated opaque cursors.
    """
    # 1. Validate sorting parameters
    if sort not in SORTABLE_FIELDS:
        raise InvalidFilterError(f"Invalid sort field '{sort}'. Allowed fields: {', '.join(sorted(SORTABLE_FIELDS.keys()))}")
    
    order = order.lower()
    if order not in ("asc", "desc"):
        raise InvalidFilterError(f"Invalid sort order '{order}'. Allowed values: 'asc', 'desc'")

    # 2. Validate limit
    if limit < 1 or limit > 100:
        raise InvalidFilterError("Limit must be between 1 and 100 inclusive.")

    # 3. Validate price filters
    if price_min is not None and price_min < 0:
        raise InvalidFilterError("priceMin must be a non-negative number.")
    if price_max is not None and price_max < 0:
        raise InvalidFilterError("priceMax must be a non-negative number.")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise InvalidFilterError(f"priceMin ({price_min}) cannot be greater than priceMax ({price_max}).")

    # Clean search query
    cleaned_search = search.strip() if search and search.strip() else None

    # 4. Build base filter conditions (parameterized)
    filter_clauses: List[str] = []
    filter_params: Dict[str, Any] = {}

    if cleaned_search:
        filter_clauses.append("(name LIKE :search OR description LIKE :search)")
        filter_params["search"] = f"%{cleaned_search}%"

    if category:
        filter_clauses.append("category = :category")
        filter_params["category"] = category

    if price_min is not None:
        filter_clauses.append("price >= :price_min")
        filter_params["price_min"] = price_min

    if price_max is not None:
        filter_clauses.append("price <= :price_max")
        filter_params["price_max"] = price_max

    if in_stock is not None:
        if in_stock:
            filter_clauses.append("stock > 0")
        else:
            filter_clauses.append("stock = 0")

    where_filter_sql = ""
    if filter_clauses:
        where_filter_sql = "WHERE " + " AND ".join(filter_clauses)

    # 5. Calculate total matching records before cursor pagination
    count_cursor = conn.cursor()
    count_query = f"SELECT COUNT(*) AS total FROM products {where_filter_sql};"
    count_cursor.execute(count_query, filter_params)
    total_count: int = count_cursor.fetchone()["total"]

    # 6. Process cursor (if provided)
    cursor_payload: Optional[Dict[str, Any]] = None
    if cursor:
        cursor_payload = decode_cursor(cursor, expected_sort=sort, expected_order=order)

    # 7. Keyset pagination condition & ordering
    # Primary sort column is `sort`, tie-breaker is `id`.
    # When navigating 'next':
    #   if order == 'asc':  (S > v OR (S = v AND id > i))
    #   if order == 'desc': (S < v OR (S = v AND id < i))
    # When navigating 'prev':
    #   if order == 'asc':  (S < v OR (S = v AND id < i)) with reverse query order (DESC)
    #   if order == 'desc': (S > v OR (S = v AND id > i)) with reverse query order (ASC)
    
    pagination_clauses: List[str] = list(filter_clauses)
    query_params: Dict[str, Any] = dict(filter_params)
    
    is_prev_nav = cursor_payload is not None and cursor_payload["d"] == "prev"

    if cursor_payload:
        cur_v = cursor_payload["v"]
        cur_i = cursor_payload["i"]
        query_params["cur_v"] = cur_v
        query_params["cur_i"] = cur_i

        if sort == "id":
            if (not is_prev_nav and order == "asc") or (is_prev_nav and order == "desc"):
                pagination_clauses.append("id > :cur_i")
            else:
                pagination_clauses.append("id < :cur_i")
        else:
            if (not is_prev_nav and order == "asc") or (is_prev_nav and order == "desc"):
                pagination_clauses.append(f"({sort} > :cur_v OR ({sort} = :cur_v AND id > :cur_i))")
            else:
                pagination_clauses.append(f"({sort} < :cur_v OR ({sort} = :cur_v AND id < :cur_i))")

    # Determine query order
    # If is_prev_nav, query in reverse order so we get items closest to the cursor
    if is_prev_nav:
        query_order_dir = "DESC" if order == "asc" else "ASC"
    else:
        query_order_dir = "ASC" if order == "asc" else "DESC"

    if sort == "id":
        order_by_sql = f"ORDER BY id {query_order_dir}"
    else:
        order_by_sql = f"ORDER BY {sort} {query_order_dir}, id {query_order_dir}"

    where_pagination_sql = ""
    if pagination_clauses:
        where_pagination_sql = "WHERE " + " AND ".join(pagination_clauses)

    fetch_limit = limit + 1
    query_sql = f"""
        SELECT id, name, description, category, price, stock, rating, createdAt
        FROM products
        {where_pagination_sql}
        {order_by_sql}
        LIMIT {fetch_limit};
    """

    data_cursor = conn.cursor()
    data_cursor.execute(query_sql, query_params)
    rows = data_cursor.fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]

    # If this was a backward navigation, we queried in reverse order, so reverse the slice back to standard order
    if is_prev_nav:
        page_rows = list(reversed(page_rows))

    products: List[Product] = [
        Product(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            category=r["category"],
            price=r["price"],
            stock=r["stock"],
            rating=r["rating"],
            createdAt=r["createdAt"],
        )
        for r in page_rows
    ]

    # Compute nextCursor and prevCursor
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None

    if cursor_payload is None:
        # First page
        prev_cursor = None
        if has_more and products:
            last_item = products[-1]
            last_val = getattr(last_item, sort)
            next_cursor = encode_cursor(last_val, last_item.id, "next", sort, order)
    elif not is_prev_nav:
        # Navigated forward with 'next' cursor
        if products:
            first_item = products[0]
            first_val = getattr(first_item, sort)
            prev_cursor = encode_cursor(first_val, first_item.id, "prev", sort, order)
            if has_more:
                last_item = products[-1]
                last_val = getattr(last_item, sort)
                next_cursor = encode_cursor(last_val, last_item.id, "next", sort, order)
            else:
                next_cursor = None
    else:
        # Navigated backward with 'prev' cursor
        if products:
            last_item = products[-1]
            last_val = getattr(last_item, sort)
            next_cursor = encode_cursor(last_val, last_item.id, "next", sort, order)
            if has_more:
                first_item = products[0]
                first_val = getattr(first_item, sort)
                prev_cursor = encode_cursor(first_val, first_item.id, "prev", sort, order)
            else:
                # Reached the first page
                prev_cursor = None

    applied = AppliedFilters(
        search=cleaned_search,
        category=category,
        priceMin=price_min,
        priceMax=price_max,
        inStock=in_stock,
        sort=sort,
        order=order,
        limit=limit,
    )

    meta = ProductMeta(
        total=total_count,
        nextCursor=next_cursor,
        prevCursor=prev_cursor,
        appliedFilters=applied,
    )

    return ProductListResponse(data=products, meta=meta)
