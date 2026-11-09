"""The join graph: an explicit map of how tables connect, plus a BFS path
finder. This is the piece that makes the SQL builder deterministic - given a
set of tables a question touches, there is exactly one shortest join path,
and it's computed the same way every time (unit-testable, no LLM guessing).
"""
from __future__ import annotations
from collections import deque

# Allowlist: only these tables/columns can ever appear in generated SQL.
# The builder and entity_resolver both check against this before touching
# any user-influenced identifier.
ALLOWED_TABLES = {
    "customers", "categories", "suppliers", "branches", "employees",
    "products", "orders", "order_items",
}

ALLOWED_COLUMNS: dict[str, set[str]] = {
    "customers":   {"id", "name", "province"},
    "categories":  {"id", "name"},
    "suppliers":   {"id", "name"},
    "branches":    {"id", "name", "region"},
    "employees":   {"id", "name", "branch_id"},
    "products":    {"id", "name", "category_id", "supplier_id", "price", "stock"},
    "orders":      {"id", "customer_id", "employee_id", "order_date", "status", "payment_method", "total"},
    "order_items": {"id", "order_id", "product_id", "qty", "unit_price"},
}

# Undirected edges: (table_a, table_b) -> ON condition (as raw column refs;
# always emitted with the psycopg.sql.Identifier wrapper, never string-formatted
# with user input).
EDGES: dict[tuple[str, str], tuple[str, str, str, str]] = {
    # (table_a, table_b): (col_a, table_b_col ... ) expressed as (a_table,a_col,b_table,b_col)
    ("orders", "customers"):    ("orders", "customer_id", "customers", "id"),
    ("orders", "employees"):    ("orders", "employee_id", "employees", "id"),
    ("orders", "order_items"):  ("order_items", "order_id", "orders", "id"),
    ("order_items", "products"): ("order_items", "product_id", "products", "id"),
    ("products", "categories"): ("products", "category_id", "categories", "id"),
    ("products", "suppliers"):  ("products", "supplier_id", "suppliers", "id"),
    ("employees", "branches"):  ("employees", "branch_id", "branches", "id"),
}


def _adjacency() -> dict[str, list[tuple[str, tuple[str, str, str, str]]]]:
    adj: dict[str, list[tuple[str, tuple[str, str, str, str]]]] = {t: [] for t in ALLOWED_TABLES}
    for (a, b), edge in EDGES.items():
        adj[a].append((b, edge))
        adj[b].append((a, edge))
    return adj


_ADJ = _adjacency()


def join_path(root: str, targets: set[str]) -> list[tuple[str, str, str, str]]:
    """BFS from `root`, returning the ordered list of join edges
    (a_table, a_col, b_table, b_col) needed to reach every table in `targets`.
    Each edge's second table is the one being newly introduced -> safe to
    emit as `JOIN b_table ON a_table.a_col = b_table.b_col` in that order.
    """
    if not targets <= ALLOWED_TABLES:
        raise ValueError(f"unknown table(s): {targets - ALLOWED_TABLES}")

    visited = {root}
    order: list[tuple[str, str, str, str]] = []
    remaining = set(targets) - {root}
    if not remaining:
        return order

    queue = deque([root])
    parent_edge: dict[str, tuple[str, str, str, str]] = {}
    parent_of: dict[str, str] = {}

    while queue and remaining:
        cur = queue.popleft()
        for nxt, edge in _ADJ[cur]:
            if nxt in visited:
                continue
            visited.add(nxt)
            parent_of[nxt] = cur
            # normalize edge so the "new" table is second
            a_t, a_c, b_t, b_c = edge
            if a_t == nxt:
                edge = (b_t, b_c, a_t, a_c)
            parent_edge[nxt] = edge
            queue.append(nxt)
            if nxt in remaining:
                remaining.discard(nxt)

    if remaining:
        missing = remaining
        raise ValueError(f"no join path from {root!r} to {missing}")

    # Reconstruct edges in BFS-discovery order for every target's ancestry.
    needed_nodes: set[str] = set()
    for t in targets:
        node = t
        while node != root and node not in needed_nodes:
            needed_nodes.add(node)
            node = parent_of[node]

    seen_edges = []
    added = set()
    for node in needed_nodes:
        edge = parent_edge[node]
        if edge[2] not in added:
            seen_edges.append(edge)
            added.add(edge[2])
    # Order by BFS distance so a table is never referenced before it's joined.
    order_index = {}
    idx = 0
    q = deque([root])
    seen = {root}
    while q:
        c = q.popleft()
        order_index[c] = idx
        idx += 1
        for nxt, _ in _ADJ[c]:
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    seen_edges.sort(key=lambda e: order_index.get(e[2], 999))
    return seen_edges
