"""Parse official Caixa Excel result files using openpyxl."""
from __future__ import annotations

from typing import List


_DRAW_COUNTS = {
    "Mega-Sena":     6,
    "Quina":         5,
    "Lotofácil":    15,
    "Lotomania":    20,
    "Timemania":     7,
    "Dupla-Sena":    6,
    "Dia de Sorte":  7,
    "Super Sete":    7,
    "+Milionária":   6,
}


def parse_excel(filepath: str, lt_name: str) -> List[dict]:
    """Parse a Caixa official Excel result file.

    Returns a list of dicts with keys: contest, date, numbers,
    and numbers2 (Dupla-Sena only).
    """
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl não instalado. Execute: pip install openpyxl")

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    expected = _DRAW_COUNTS.get(lt_name, 6)
    results: List[dict] = []
    header_skipped = False

    for row in ws.iter_rows(values_only=True):
        if not row or row[0] is None:
            continue

        # Skip header row(s) — first column will be non-integer
        if not header_skipped:
            header_skipped = True
            try:
                int(str(row[0]).strip())
            except (TypeError, ValueError):
                continue

        try:
            contest = str(int(str(row[0]).strip()))
        except (TypeError, ValueError):
            continue

        # Date in column 1
        date_raw = row[1] if len(row) > 1 else None
        if hasattr(date_raw, "strftime"):
            date = date_raw.strftime("%d/%m/%Y")
        elif isinstance(date_raw, str) and date_raw.strip():
            date = date_raw.strip()
            if len(date) == 10 and date[4] == "-":
                y, m, d = date.split("-")
                date = f"{d}/{m}/{y}"
        else:
            date = ""

        # Collect integers from remaining columns
        numbers: List[int] = []
        for val in row[2:]:
            if val is None:
                continue
            try:
                n = int(str(val).strip())
                if 1 <= n <= 99:
                    numbers.append(n)
            except (TypeError, ValueError):
                continue

        if not numbers:
            continue

        result: dict = {"contest": contest, "date": date}
        if lt_name == "Dupla-Sena" and len(numbers) >= expected * 2:
            result["numbers"]  = sorted(numbers[:expected])
            result["numbers2"] = sorted(numbers[expected : expected * 2])
        else:
            result["numbers"] = sorted(numbers[:expected])

        results.append(result)

    wb.close()
    return results
