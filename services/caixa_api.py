"""Fetches official draw results from Caixa Econômica Federal.

Strategy:
  1. Try the official Caixa API (servicebus.caixa.gov.br).
  2. On failure, fall back to the community wrapper (loteriascaixa-api.herokuapp.com).
"""
from __future__ import annotations

import requests
from typing import Optional

# ── slugs ──────────────────────────────────────────────────────────────────

SLUGS = {
    "Mega-Sena":     "megasena",
    "Quina":         "quina",
    "Lotofácil":     "lotofacil",
    "Lotomania":     "lotomania",
    "Timemania":     "timemania",
    "Dupla-Sena":    "duplasena",
    "Dia de Sorte":  "diadesorte",
    "Super Sete":    "supersete",
    "+Milionária":   "maismilionaria",
}

_OFFICIAL  = "https://servicebus.caixa.gov.br/portaldeloterias/api"
_COMMUNITY = "https://loteriascaixa-api.herokuapp.com/api"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://loterias.caixa.gov.br/",
}

# Month names returned by the API (title-case)
_MONTHS_PT = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
    "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12,
    # uppercase fallback
    "JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4,
    "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
    "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}

# Dupla-Sena: how many numbers per draw
_DUPLA_DRAW = 6


# ── low-level HTTP ─────────────────────────────────────────────────────────

def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12, verify=True)
        r.raise_for_status()
        raw = r.json()
        # community wrapper returns a list; take the first (= latest) element
        return raw[0] if isinstance(raw, list) else raw
    except Exception:
        return None


def _official_url(slug: str, contest: int | str | None) -> str:
    base = f"{_OFFICIAL}/{slug}"
    return f"{base}/{contest}" if contest else base


def _community_url(slug: str, contest: int | str | None) -> str:
    base = f"{_COMMUNITY}/{slug}"
    return f"{base}/{contest}" if contest else base


def _fetch(lt_name: str, contest: int | str | None = None) -> Optional[dict]:
    slug = SLUGS.get(lt_name)
    if not slug:
        return None
    data = _get(_official_url(slug, contest))
    if data:
        data["_source"] = "official"
        return data
    data = _get(_community_url(slug, contest))
    if data:
        data["_source"] = "community"
    return data


# ── public helpers ─────────────────────────────────────────────────────────

def fetch_latest(lt_name: str) -> Optional[dict]:
    return _fetch(lt_name)


def fetch_contest(lt_name: str, contest: int | str) -> Optional[dict]:
    return _fetch(lt_name, contest)


# ── parsing ────────────────────────────────────────────────────────────────

def _parse_nums(raw) -> list[int]:
    if not raw:
        return []
    try:
        return [int(n) for n in raw]
    except (TypeError, ValueError):
        return []


def _find_team_id(name: str) -> Optional[int]:
    """Match a team name string (possibly 'TEAM /STATE') to a team ID."""
    from models.lottery_types import TIMEMANIA_TEAMS
    norm = name.upper().split("/")[0].strip()
    for tid, tname in TIMEMANIA_TEAMS.items():
        if tname.upper() == norm:
            return tid
    # partial match fallback
    for tid, tname in TIMEMANIA_TEAMS.items():
        if norm in tname.upper() or tname.upper() in norm:
            return tid
    return None


def parse(data: dict, lt_name: str) -> Optional[dict]:
    """Normalise a raw API response (official or community) into a plain dict."""
    if not data:
        return None
    try:
        source = data.get("_source", "official")

        # ── contest & date ──────────────────────────────────────────────
        contest = str(data.get("concurso") or data.get("numero") or "")
        date    = data.get("data") or data.get("dataApuracao") or ""
        # official API may return ISO; community already returns dd/MM/yyyy
        if date and date.count("-") == 2:
            y, m, d = date.split("-")
            date = f"{d}/{m}/{y}"

        # ── main numbers ────────────────────────────────────────────────
        # Prefer dezenasOrdemSorteio (draw order) when available;
        # for Dupla-Sena it contains BOTH draws concatenated (12 numbers).
        raw_nums = (data.get("dezenas")
                    or data.get("dezenasOrdemSorteio")
                    or data.get("dezenasSorteadasOrdemSorteio")
                    or data.get("listaDezenas")
                    or [])

        if lt_name == "Dupla-Sena":
            all_nums = _parse_nums(raw_nums)
            if len(all_nums) >= _DUPLA_DRAW * 2:
                numbers  = sorted(all_nums[:_DUPLA_DRAW])
                numbers2 = sorted(all_nums[_DUPLA_DRAW:_DUPLA_DRAW * 2])
            elif len(all_nums) >= _DUPLA_DRAW:
                numbers  = sorted(all_nums[:_DUPLA_DRAW])
                numbers2 = None
            else:
                return None
        else:
            numbers = sorted(_parse_nums(raw_nums))
            if not numbers:
                return None
            numbers2 = None

        out: dict = {
            "numbers":     numbers,
            "numbers2":    numbers2,
            "contest":     contest,
            "date":        date,
            "accumulated": bool(data.get("acumulou") or data.get("acumulado")),
        }

        nxt = (data.get("valorEstimadoProximoConcurso")
               or data.get("valorAcumuladoProximoConcurso"))
        if nxt:
            try:
                out["next_prize"] = float(nxt)
            except (TypeError, ValueError):
                pass

        # ── extras ─────────────────────────────────────────────────────
        if lt_name == "Timemania":
            team = (data.get("timeCoracao") or "").strip()
            out["extra"]       = _find_team_id(team)
            out["extra_label"] = team

        elif lt_name == "Dia de Sorte":
            mes = (data.get("mesSorte") or data.get("nomeTimeCoracaoMesSorte") or "").strip()
            out["extra"]       = _MONTHS_PT.get(mes)
            out["extra_label"] = mes

        elif lt_name == "+Milionária":
            trevos = _parse_nums(
                data.get("trevos")
                or data.get("trevosSorteadosOrdemSorteio")
                or []
            )
            if trevos:
                out["trevos"] = sorted(trevos)

        return out

    except Exception:
        return None
