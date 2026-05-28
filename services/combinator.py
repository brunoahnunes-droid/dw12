"""Combinatorial game generator (desdobramento) with moldura/miolo classification."""
from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from models.lottery_types import LotteryType, LOTTERY_CONFIGS

# ─── Soma histórica por loteria ───────────────────────────────────────────────
SOMA_RANGES = {
    'Lotofácil':    (171, 220),
    'Mega-Sena':    (100, 200),
    'Quina':        (100, 230),
    'Lotomania':    (800, 1200),
    'Dupla-Sena':   (100, 200),
    'Timemania':    (150, 280),
    'Dia de Sorte': (80, 180),
    '+Milionária':  (100, 200),
    'Super Sete':   (15, 50),
}


def soma_sugerida(lt_name: str) -> Tuple[Optional[int], Optional[int]]:
    return SOMA_RANGES.get(lt_name, (None, None))


# ─── Filtros de acertabilidade ────────────────────────────────────────────────

def filtro_soma(combo, lo, hi) -> bool:
    """Retorna True se a soma está no intervalo histórico esperado."""
    s = sum(combo)
    return lo <= s <= hi


def filtro_paridade(combo, min_par, max_par) -> bool:
    """Retorna True se o nº de pares está dentro do intervalo."""
    pares = sum(1 for n in combo if n % 2 == 0)
    return min_par <= pares <= max_par


def filtro_consecutivos(combo, max_seq: int = 2) -> bool:
    """Retorna True se não há sequência de mais de max_seq consecutivos."""
    s = sorted(combo)
    seq = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1] + 1:
            seq += 1
            if seq > max_seq:
                return False
        else:
            seq = 1
    return True


def aplicar_filtros(combos, cfg_filtros: dict, lo=None, hi=None) -> list:
    """Aplica todos os filtros ativos. cfg_filtros é um dict com as opções."""
    resultado = []
    for c in combos:
        ok = True
        if cfg_filtros.get('soma'):
            ok = ok and filtro_soma(c, cfg_filtros['soma_min'], cfg_filtros['soma_max'])
        if cfg_filtros.get('paridade'):
            ok = ok and filtro_paridade(c, cfg_filtros['par_min'], cfg_filtros['par_max'])
        if cfg_filtros.get('consecutivos'):
            ok = ok and filtro_consecutivos(c, cfg_filtros['max_seq'])
        if ok:
            resultado.append(c)
    return resultado


def score_combo(combo, moldura: Set[int], cfg_filtros: dict, lt_name: str) -> int:
    """Retorna score 0-100 baseado em quantos filtros o jogo atende."""
    pontos = 0
    total = 0
    lo_s, hi_s = soma_sugerida(lt_name)
    if lo_s is not None:
        total += 1
        if filtro_soma(combo, lo_s, hi_s):
            pontos += 1
    k = len(combo)
    total += 1
    pares = sum(1 for n in combo if n % 2 == 0)
    if abs(pares - k / 2) <= 1:
        pontos += 1
    total += 1
    if filtro_consecutivos(combo, 2):
        pontos += 1
    return round(pontos / total * 100) if total else 0


# Number of columns per row on the physical lottery card
_COLS: Dict[LotteryType, int] = {
    LotteryType.MEGA_SENA:        10,
    LotteryType.QUINA:            10,
    LotteryType.LOTOFACIL:         5,
    LotteryType.LOTOMANIA:        10,
    LotteryType.TIMEMANIA:        10,
    LotteryType.DUPLA_SENA:       10,
    LotteryType.DIA_DE_SORTE:      8,
    LotteryType.SUPER_SETE:        7,
    LotteryType.MAIS_MILIONARIA:  10,
}

MAX_COMBOS = 5_000   # cap on combinations held in memory


def grid_cols(lt: LotteryType) -> int:
    return _COLS.get(lt, 10)


def compute_moldura(lt: LotteryType) -> Tuple[Set[int], Set[int]]:
    """Return (moldura_set, miolo_set) based on the card's border/center split."""
    cfg  = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    cols = grid_cols(lt)
    all_nums = list(range(lo, hi + 1))
    rows = math.ceil(len(all_nums) / cols)

    def cell(r: int, c: int) -> Optional[int]:
        i = r * cols + c
        return all_nums[i] if i < len(all_nums) else None

    moldura: Set[int] = set()
    for r in range(rows):
        for c in range(cols):
            n = cell(r, c)
            if n is None:
                continue
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                moldura.add(n)

    return moldura, set(all_nums) - moldura


def build_grid(lt: LotteryType) -> List[List[Optional[int]]]:
    """Return numbers as a 2-D grid matching the card layout."""
    cfg = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    cols = grid_cols(lt)
    all_nums = list(range(lo, hi + 1))
    rows = math.ceil(len(all_nums) / cols)
    grid: List[List[Optional[int]]] = []
    for r in range(rows):
        row: List[Optional[int]] = []
        for c in range(cols):
            i = r * cols + c
            row.append(all_nums[i] if i < len(all_nums) else None)
        grid.append(row)
    return grid


def combine_groups(
    mol_nums: List[int],
    mio_nums: List[int],
    k_mol: int,
    k_mio: int,
    max_games: Optional[int] = None,
    fixed_mol: Optional[List[int]] = None,
    fixed_mio: Optional[List[int]] = None,
) -> Tuple[List[Tuple[int, ...]], int, bool]:
    """
    Generate games picking k_mol from moldura pool and k_mio from miolo pool.
    fixed_mol: números da moldura que aparecem em todos os jogos.
    fixed_mio: números do miolo que aparecem em todos os jogos.
    Returns (combos, total_possible, truncated).
    """
    from itertools import product as iproduct

    fixed_mol = list(fixed_mol or [])
    fixed_mio = list(fixed_mio or [])

    # Remove fixas do pool variável
    mol_pool = [n for n in mol_nums if n not in fixed_mol]
    mio_pool = [n for n in mio_nums if n not in fixed_mio]

    # Ajusta quantas variáveis precisamos
    k_mol_var = k_mol - len(fixed_mol)
    k_mio_var = k_mio - len(fixed_mio)

    if k_mol_var < 0 or k_mio_var < 0:
        return [], 0, False
    if k_mol_var == 0 and k_mio_var == 0:
        return [tuple(sorted(fixed_mol + fixed_mio))], 1, False

    mol_combos = list(combinations(sorted(mol_pool), k_mol_var)) if k_mol_var > 0 else [()]
    mio_combos = list(combinations(sorted(mio_pool), k_mio_var)) if k_mio_var > 0 else [()]
    total = len(mol_combos) * len(mio_combos)
    limit = min(max_games or MAX_COMBOS, MAX_COMBOS)

    base = tuple(sorted(fixed_mol + fixed_mio))

    if total <= limit:
        result = [tuple(sorted(base + m + mi)) for m, mi in iproduct(mol_combos, mio_combos)]
        return result, total, False

    # Random sampling
    seen: set = set()
    out: List[Tuple[int, ...]] = []
    attempts = 0
    max_attempts = limit * 40
    while len(out) < limit and attempts < max_attempts:
        m  = random.choice(mol_combos)
        mi = random.choice(mio_combos)
        c  = tuple(sorted(base + m + mi))
        if c not in seen:
            seen.add(c)
            out.append(c)
        attempts += 1

    return out, total, True


def combo_stats(combo: Tuple[int, ...], moldura: Set[int]) -> Tuple[int, int]:
    """Return (n_moldura, n_miolo) for a combo."""
    m = len(set(combo) & moldura)
    return m, len(combo) - m
