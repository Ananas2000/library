import tkinter as tk
from tkinter import ttk
from typing import Any, List, Optional, Sequence, Tuple


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _try_num(v: str):
    s = (v or "").strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


class TreeviewGridController:
    """
    - Click header: sort ASC/DESC
    - Search: substring filter across ALL columns
    """
    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.columns: List[str] = list(tree["columns"])
        self.all_rows: List[Tuple[Any, ...]] = []

        # sorting
        self.sort_col: Optional[str] = None
        self.sort_desc: bool = False

        # search
        self.search_text: str = ""

        self.tree.bind("<Button-1>", self._on_click, add=True)

    def set_data(self, rows: Sequence[Tuple[Any, ...]]):
        self.columns = list(self.tree["columns"])
        self.all_rows = list(rows)
        self.apply()

    def set_search(self, text: str):
        self.search_text = (text or "").strip().lower()
        self.apply()

    def clear_search(self):
        self.search_text = ""
        self.apply()

    def apply(self):
        rows = self._searched_rows()
        rows = self._sorted_rows(rows)
        self._render(rows)

    # ---------- render ----------
    def _render(self, rows: List[Tuple[Any, ...]]):
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", values=row)

    # ---------- search ----------
    def _searched_rows(self) -> List[Tuple[Any, ...]]:
        q = self.search_text
        if not q:
            return list(self.all_rows)

        out: List[Tuple[Any, ...]] = []
        for row in self.all_rows:
            # ищем подстроку по всем значениям
            hay = " | ".join(_to_str(x).lower() for x in row)
            if q in hay:
                out.append(row)
        return out

    # ---------- sorting ----------
    def _sorted_rows(self, rows: List[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
        if not self.sort_col or self.sort_col not in self.columns:
            return rows
        i = self.columns.index(self.sort_col)

        def key_fn(r):
            s = _to_str(r[i])
            n = _try_num(s)
            return (0, n) if n is not None else (1, s.lower())

        return sorted(rows, key=key_fn, reverse=self.sort_desc)

    def _on_click(self, event: tk.Event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        col_id = self.tree.identify_column(event.x)  # '#1'...
        try:
            col_index = int(col_id.replace("#", "")) - 1
        except Exception:
            return

        cols = list(self.tree["columns"])
        if col_index < 0 or col_index >= len(cols):
            return

        col = cols[col_index]

        # toggle sort
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False

        self.apply()
        return "break"
