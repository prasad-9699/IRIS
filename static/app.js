/**
 * Production Product Catalog - Frontend Engine
 * Keyset cursor pagination, multi-field filtering, full-text search, and full URL state sync.
 */

(() => {
  // Application State
  const state = {
    search: '',
    category: '',
    priceMin: '',
    priceMax: '',
    inStock: '',
    sort: 'createdAt',
    order: 'desc',
    limit: 20,
    cursor: null,
  };

  let nextCursor = null;
  let prevCursor = null;
  let searchDebounceTimer = null;

  // DOM Elements Cache
  const elements = {
    // Top Stats
    statTotalProducts: document.getElementById('stat-total-products'),
    statActiveSort: document.getElementById('stat-active-sort'),
    statPageWindow: document.getElementById('stat-page-window'),
    statCursorState: document.getElementById('stat-cursor-state'),
    statActiveFiltersCount: document.getElementById('stat-active-filters-count'),
    systemStatusText: document.getElementById('system-status-text'),

    // Filters
    searchInput: document.getElementById('search-input'),
    searchClearBtn: document.getElementById('search-clear-btn'),
    categorySelect: document.getElementById('category-select'),
    priceMinInput: document.getElementById('price-min-input'),
    priceMaxInput: document.getElementById('price-max-input'),
    stockSelect: document.getElementById('stock-select'),
    limitSelect: document.getElementById('limit-select'),
    applyFiltersBtn: document.getElementById('apply-filters-btn'),
    resetFiltersBtn: document.getElementById('reset-filters-btn'),

    // Table & States
    productTable: document.getElementById('product-table'),
    productTbody: document.getElementById('product-tbody'),
    tableResultsSummary: document.getElementById('table-results-summary'),
    loadingState: document.getElementById('loading-spinner-state'),
    emptyState: document.getElementById('empty-state'),
    emptyResetBtn: document.getElementById('empty-reset-btn'),
    errorBanner: document.getElementById('error-banner'),
    errorMessageText: document.getElementById('error-message-text'),
    dismissErrorBtn: document.getElementById('dismiss-error-btn'),

    // Pagination Controls
    prevPageBtn: document.getElementById('prev-page-btn'),
    nextPageBtn: document.getElementById('next-page-btn'),
    paginationIndicator: document.getElementById('pagination-indicator'),
    bottomPrevPageBtn: document.getElementById('bottom-prev-page-btn'),
    bottomNextPageBtn: document.getElementById('bottom-next-page-btn'),
    bottomPaginationIndicator: document.getElementById('bottom-pagination-indicator'),
  };

  /**
   * Currency formatter for Indian Rupees (₹)
   */
  const currencyFormatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });

  /**
   * Format ISO date string nicely
   */
  function formatDate(isoStr) {
    if (!isoStr) return '--';
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoStr;
    }
  }

  /**
   * Get category CSS badge class
   */
  function getCategoryClass(cat) {
    const slug = (cat || '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
    if (slug.includes('electronics')) return 'cat-electronics';
    if (slug.includes('home') || slug.includes('kitchen')) return 'cat-home-kitchen';
    if (slug.includes('fashion')) return 'cat-fashion';
    if (slug.includes('sports')) return 'cat-sports';
    if (slug.includes('books')) return 'cat-books';
    if (slug.includes('beauty')) return 'cat-beauty';
    return 'cat-default';
  }

  /**
   * Show error alert banner
   */
  function showError(msg) {
    elements.errorMessageText.textContent = msg;
    elements.errorBanner.classList.remove('hidden');
  }

  /**
   * Hide error alert banner
   */
  function hideError() {
    elements.errorBanner.classList.add('hidden');
    elements.errorMessageText.textContent = '';
  }

  /**
   * Read URL Search Params and populate application state
   */
  function readStateFromURL() {
    const params = new URLSearchParams(window.location.search);

    state.search = params.get('search') || '';
    state.category = params.get('category') || '';
    state.priceMin = params.get('priceMin') || '';
    state.priceMax = params.get('priceMax') || '';
    state.inStock = params.get('inStock') || '';
    state.sort = params.get('sort') || 'createdAt';
    state.order = (params.get('order') || 'desc').toLowerCase();
    state.limit = parseInt(params.get('limit'), 10) || 20;
    state.cursor = params.get('cursor') || null;

    // Validate limit boundaries
    if (state.limit < 1 || state.limit > 100) {
      state.limit = 20;
    }

    // Populate DOM controls to match state
    elements.searchInput.value = state.search;
    elements.searchClearBtn.style.display = state.search ? 'block' : 'none';
    elements.categorySelect.value = state.category;
    elements.priceMinInput.value = state.priceMin;
    elements.priceMaxInput.value = state.priceMax;
    elements.stockSelect.value = state.inStock;
    elements.limitSelect.value = state.limit.toString();

    updateSortHeaderIndicators();
  }

  /**
   * Synchronize application state into browser URL using URLSearchParams
   */
  function syncStateToURL(push = true) {
    const params = new URLSearchParams();

    if (state.search.trim()) params.set('search', state.search.trim());
    if (state.category) params.set('category', state.category);
    if (state.priceMin !== '' && state.priceMin !== null) params.set('priceMin', state.priceMin);
    if (state.priceMax !== '' && state.priceMax !== null) params.set('priceMax', state.priceMax);
    if (state.inStock !== '' && state.inStock !== null) params.set('inStock', state.inStock);

    if (state.sort && state.sort !== 'createdAt') params.set('sort', state.sort);
    if (state.order && state.order !== 'desc') params.set('order', state.order);
    if (state.limit && state.limit !== 20) params.set('limit', state.limit.toString());
    if (state.cursor) params.set('cursor', state.cursor);

    const queryString = params.toString();
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;

    if (push) {
      window.history.pushState({}, '', newUrl);
    } else {
      window.history.replaceState({}, '', newUrl);
    }

    updateStatsBar();
  }

  /**
   * Update visual indicators on sortable table headers
   */
  function updateSortHeaderIndicators() {
    const headers = document.querySelectorAll('.sortable-th');
    headers.forEach(th => {
      const col = th.getAttribute('data-column');
      const icon = th.querySelector('.sort-icon');
      if (col === state.sort) {
        th.classList.add('active-sort');
        icon.textContent = state.order === 'asc' ? '▲' : '▼';
      } else {
        th.classList.remove('active-sort');
        icon.textContent = '⇅';
      }
    });

    elements.statActiveSort.textContent = `${state.sort} (${state.order.toUpperCase()})`;
  }

  /**
   * Update summary stat cards
   */
  function updateStatsBar(total = null) {
    if (total !== null) {
      elements.statTotalProducts.textContent = total.toLocaleString();
    }

    elements.statPageWindow.textContent = `Page Size: ${state.limit}`;
    elements.statCursorState.textContent = state.cursor ? 'Cursor Filter Active' : 'First Page';

    let activeCount = 0;
    if (state.search.trim()) activeCount++;
    if (state.category) activeCount++;
    if (state.priceMin !== '') activeCount++;
    if (state.priceMax !== '') activeCount++;
    if (state.inStock !== '') activeCount++;

    elements.statActiveFiltersCount.textContent = `${activeCount} Active`;
  }

  /**
   * Fetch categories from /api/categories and populate dropdown
   */
  async function loadCategories() {
    try {
      const res = await fetch('/api/categories');
      if (!res.ok) throw new Error('Failed to load categories');
      const categories = await res.json();

      // Clear existing except 'All'
      elements.categorySelect.innerHTML = '<option value="">All Categories</option>';
      categories.forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = cat;
        elements.categorySelect.appendChild(opt);
      });

      // Restore selected category if state has it
      if (state.category) {
        elements.categorySelect.value = state.category;
      }
    } catch (err) {
      console.error('Error fetching categories:', err);
    }
  }

  /**
   * Verify system health and database connectivity
   */
  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        elements.systemStatusText.textContent = `Connected (${data.totalProducts} items)`;
      } else {
        elements.systemStatusText.textContent = 'Service Degraded';
      }
    } catch {
      elements.systemStatusText.textContent = 'Offline';
    }
  }

  /**
   * Fetch products from API based on active state
   */
  async function fetchProducts() {
    hideError();
    elements.loadingState.classList.remove('hidden');
    elements.emptyState.classList.add('hidden');
    elements.productTbody.innerHTML = '';

    const params = new URLSearchParams();
    if (state.search.trim()) params.set('search', state.search.trim());
    if (state.category) params.set('category', state.category);
    if (state.priceMin !== '' && state.priceMin !== null) params.set('priceMin', state.priceMin);
    if (state.priceMax !== '' && state.priceMax !== null) params.set('priceMax', state.priceMax);
    if (state.inStock !== '' && state.inStock !== null) params.set('inStock', state.inStock);
    if (state.sort) params.set('sort', state.sort);
    if (state.order) params.set('order', state.order);
    if (state.limit) params.set('limit', state.limit.toString());
    if (state.cursor) params.set('cursor', state.cursor);

    try {
      const response = await fetch(`/api/products?${params.toString()}`);
      const result = await response.json();

      elements.loadingState.classList.add('hidden');

      if (!response.ok) {
        const errorDetail = result.detail || 'Failed to fetch products';
        showError(errorDetail);
        updatePaginationButtons(null, null);
        elements.tableResultsSummary.textContent = 'Error loading results';
        return;
      }

      const products = result.data || [];
      const meta = result.meta || {};

      nextCursor = meta.nextCursor || null;
      prevCursor = meta.prevCursor || null;

      updateStatsBar(meta.total);
      updatePaginationButtons(prevCursor, nextCursor);

      if (products.length === 0) {
        elements.emptyState.classList.remove('hidden');
        elements.tableResultsSummary.textContent = 'Showing 0 matching products';
      } else {
        renderTableRows(products);
        elements.tableResultsSummary.textContent = `Showing ${products.length} of ${meta.total.toLocaleString()} products`;
      }
    } catch (err) {
      elements.loadingState.classList.add('hidden');
      showError(`Network connection error: ${err.message}`);
      console.error(err);
    }
  }

  /**
   * Render product rows in the table
   */
  function renderTableRows(products) {
    const fragment = document.createDocumentFragment();

    products.forEach(p => {
      const tr = document.createElement('tr');

      // ID
      const tdId = document.createElement('td');
      tdId.className = 'col-id';
      tdId.textContent = `#${p.id}`;

      // Name
      const tdName = document.createElement('td');
      tdName.className = 'col-name';
      tdName.textContent = p.name;

      // Description
      const tdDesc = document.createElement('td');
      tdDesc.className = 'col-description';
      tdDesc.textContent = p.description;
      tdDesc.title = p.description;

      // Category
      const tdCategory = document.createElement('td');
      const catBadge = document.createElement('span');
      catBadge.className = `category-badge ${getCategoryClass(p.category)}`;
      catBadge.textContent = p.category;
      tdCategory.appendChild(catBadge);

      // Price
      const tdPrice = document.createElement('td');
      tdPrice.className = 'col-price';
      tdPrice.textContent = currencyFormatter.format(p.price);

      // Stock
      const tdStock = document.createElement('td');
      const stockContainer = document.createElement('div');
      stockContainer.className = 'stock-status-cell';

      const isAvailable = p.stock > 0;
      const stockBadge = document.createElement('span');
      stockBadge.className = `stock-badge ${isAvailable ? 'stock-in' : 'stock-out'}`;
      stockBadge.innerHTML = `<span class="dot"></span> ${isAvailable ? 'In Stock' : 'Out of Stock'}`;

      const stockQty = document.createElement('span');
      stockQty.className = 'stock-qty';
      stockQty.textContent = isAvailable ? `(${p.stock})` : '';

      stockContainer.appendChild(stockBadge);
      if (isAvailable) stockContainer.appendChild(stockQty);
      tdStock.appendChild(stockContainer);

      // Rating
      const tdRating = document.createElement('td');
      const ratingPill = document.createElement('span');
      ratingPill.className = 'rating-pill';
      ratingPill.innerHTML = `<span class="star-icon">★</span> ${p.rating.toFixed(1)}`;
      tdRating.appendChild(ratingPill);

      // Created Date
      const tdDate = document.createElement('td');
      tdDate.className = 'col-date';
      tdDate.textContent = formatDate(p.createdAt);

      tr.appendChild(tdId);
      tr.appendChild(tdName);
      tr.appendChild(tdDesc);
      tr.appendChild(tdCategory);
      tr.appendChild(tdPrice);
      tr.appendChild(tdStock);
      tr.appendChild(tdRating);
      tr.appendChild(tdDate);

      fragment.appendChild(tr);
    });

    elements.productTbody.appendChild(fragment);
  }

  /**
   * Update pagination Previous and Next buttons state
   */
  function updatePaginationButtons(prev, next) {
    const hasPrev = Boolean(prev);
    const hasNext = Boolean(next);

    elements.prevPageBtn.disabled = !hasPrev;
    elements.nextPageBtn.disabled = !hasNext;
    elements.bottomPrevPageBtn.disabled = !hasPrev;
    elements.bottomNextPageBtn.disabled = !hasNext;

    const pageLabel = state.cursor ? 'Navigated Page' : 'Page 1';
    elements.paginationIndicator.textContent = pageLabel;
    elements.bottomPaginationIndicator.textContent = pageLabel;
  }

  /**
   * Setup Event Listeners
   */
  function setupEventListeners() {
    // 1. Debounced Search Input
    elements.searchInput.addEventListener('input', e => {
      const val = e.target.value;
      elements.searchClearBtn.style.display = val ? 'block' : 'none';

      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        state.search = val;
        state.cursor = null; // Always reset cursor on filter change
        syncStateToURL(false); // replaceState for typing
        fetchProducts();
      }, 350);
    });

    // Clear Search Button
    elements.searchClearBtn.addEventListener('click', () => {
      elements.searchInput.value = '';
      elements.searchClearBtn.style.display = 'none';
      state.search = '';
      state.cursor = null;
      syncStateToURL(true);
      fetchProducts();
    });

    // 2. Filter Controls (Category, Stock, Limit)
    elements.categorySelect.addEventListener('change', () => {
      state.category = elements.categorySelect.value;
      state.cursor = null;
      syncStateToURL(true);
      fetchProducts();
    });

    elements.stockSelect.addEventListener('change', () => {
      state.inStock = elements.stockSelect.value;
      state.cursor = null;
      syncStateToURL(true);
      fetchProducts();
    });

    elements.limitSelect.addEventListener('change', () => {
      state.limit = parseInt(elements.limitSelect.value, 10);
      state.cursor = null;
      syncStateToURL(true);
      fetchProducts();
    });

    // 3. Apply Filters Button (for prices or manual form trigger)
    elements.applyFiltersBtn.addEventListener('click', () => {
      state.search = elements.searchInput.value;
      state.category = elements.categorySelect.value;
      state.priceMin = elements.priceMinInput.value;
      state.priceMax = elements.priceMaxInput.value;
      state.inStock = elements.stockSelect.value;
      state.limit = parseInt(elements.limitSelect.value, 10);
      state.cursor = null;

      syncStateToURL(true);
      fetchProducts();
    });

    // Allow Enter key in price inputs to trigger apply
    [elements.priceMinInput, elements.priceMaxInput].forEach(inp => {
      inp.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          e.preventDefault();
          elements.applyFiltersBtn.click();
        }
      });
    });

    // 4. Reset Filters Button
    const resetAll = () => {
      state.search = '';
      state.category = '';
      state.priceMin = '';
      state.priceMax = '';
      state.inStock = '';
      state.sort = 'createdAt';
      state.order = 'desc';
      state.limit = 20;
      state.cursor = null;

      elements.searchInput.value = '';
      elements.searchClearBtn.style.display = 'none';
      elements.categorySelect.value = '';
      elements.priceMinInput.value = '';
      elements.priceMaxInput.value = '';
      elements.stockSelect.value = '';
      elements.limitSelect.value = '20';

      updateSortHeaderIndicators();
      syncStateToURL(true);
      fetchProducts();
    };

    elements.resetFiltersBtn.addEventListener('click', resetAll);
    elements.emptyResetBtn.addEventListener('click', resetAll);

    // 5. Sort Headers Click
    document.querySelectorAll('.sortable-th').forEach(th => {
      th.addEventListener('click', () => {
        const column = th.getAttribute('data-column');
        if (state.sort === column) {
          // Toggle order
          state.order = state.order === 'asc' ? 'desc' : 'asc';
        } else {
          state.sort = column;
          // Natural default: descending for date/rating/price/stock/id, ascending for text
          state.order = ['name', 'description', 'category'].includes(column) ? 'asc' : 'desc';
        }

        state.cursor = null; // Invalidate cursor on sort change
        updateSortHeaderIndicators();
        syncStateToURL(true);
        fetchProducts();
      });
    });

    // 6. Keyset Pagination Handlers (Top and Bottom)
    const handleNext = () => {
      if (nextCursor) {
        state.cursor = nextCursor;
        syncStateToURL(true);
        fetchProducts();
      }
    };

    const handlePrev = () => {
      if (prevCursor) {
        state.cursor = prevCursor;
        syncStateToURL(true);
        fetchProducts();
      }
    };

    elements.nextPageBtn.addEventListener('click', handleNext);
    elements.bottomNextPageBtn.addEventListener('click', handleNext);
    elements.prevPageBtn.addEventListener('click', handlePrev);
    elements.bottomPrevPageBtn.addEventListener('click', handlePrev);

    // 7. Browser Back & Forward Navigation (popstate)
    window.addEventListener('popstate', () => {
      readStateFromURL();
      fetchProducts();
    });

    // 8. Dismiss Error Banner
    elements.dismissErrorBtn.addEventListener('click', hideError);
  }

  /**
   * Application Initialization
   */
  async function init() {
    await loadCategories();
    readStateFromURL();
    await checkHealth();
    setupEventListeners();
    await fetchProducts();
  }

  // Launch when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
