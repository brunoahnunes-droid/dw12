"""Fetches official draw results from the Caixa Econômica Federal API."""
from __future__ import annotations

import requests
from typing import Optional

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

BASE = "https://servicebus.caixa.gov.br/portaldeloterias/api"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://loterias.caixa.gov.br/",
    "Origin":  "https://loterias.caixa.gov.br",
}

_MONTHS_PT = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4,
    "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
    "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}


def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12, verify=True)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_latest(lt_name: str) -> Optional[dict]:
    slug = SLUGS.get(lt_name)
    return _get(f"{BASE}/{slug}") if slug else None


def fetch_contest(lt_name: str, contest: int | str) -> Optional[dict]:
    slug = SLUGS.get(lt_name)
    return _get(f"{BASE}/{slug}/{contest}") if slug else None


def _parse_nums(raw) -> list[int]:
    if not raw:
        return []
    try:
        return sorted(int(n) for n in raw)
    except (TypeError, ValueError):
        return []


def parse(data: dict, lt_name: str) -> Optional[dict]:
    """Normalise Caixa API response into a plain dict."""
    if not data:
        return None
    try:
        numbers = _parse_nums(
            data.get("dezenasSorteadasOrdemSorteio")
            or data.get("listaDezenas")
            or data.get("dezenas")
        )
        if not numbers:
            return None

        contest = str(data.get("numero") or data.get("concurso") or "")
        date = data.get("dataApuracao", "")
        # normalise ISO → dd/MM/yyyy
        if date and date.count("-") == 2:
            y, m, d = date.split("-")
            date = f"{d}/{m}/{y}"

        out: dict = {
            "numbers": numbers,
            "contest": contest,
            "date": date,
            "accumulated": bool(data.get("acumulado")),
        }

        nxt = data.get("valorEstimadoProximoConcurso") or \
              data.get("valorAcumuladoProximoConcurso")
        if nxt:
            try:
                out["next_prize"] = float(nxt)
            except (TypeError, ValueError):
                pass

        if lt_name == "Dupla-Sena":
            nums2 = _parse_nums(data.get("dezenas2") or data.get("listaDezenas2"))
            if nums2:
                out["numbers2"] = nums2

        if lt_name == "Timemania":
            from models.lottery_types import TIMEMANIA_TEAMS
            team = (data.get("nomeTimeCoracaoMesSorte") or "").strip()
            for tid, tname in TIMEMANIA_TEAMS.items():
                if tname.upper() == team.upper():
                    out["extra"] = tid
                    break
            out["extra_label"] = team

        elif lt_name == "Dia de Sorte":
            month = (data.get("nomeTimeCoracaoMesSorte") or "").upper()
            out["extra"] = _MONTHS_PT.get(month)
            out["extra_label"] = month.capitalize()

        elif lt_name == "+Milionária":
            trevos = _parse_nums(
                data.get("trevos") or data.get("trevosSorteadosOrdemSorteio")
            )
            if trevos:
                out["trevos"] = trevos

        return out
    except Exception:
        return None
