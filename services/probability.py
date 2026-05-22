from math import comb, log2
from typing import List, Dict, Any
from models.lottery_types import LotteryConfig, LotteryType, PrizeTier


def hyper_pmf(N: int, K: int, n: int, k: int) -> float:
    """P(X=k) for hypergeometric(N, K, n).

    N = population, K = player picks ("successes"), n = draw size, k = matches.
    """
    if k < max(0, K + n - N) or k > min(K, n):
        return 0.0
    denom = comb(N, n)
    return comb(K, k) * comb(N - K, n - k) / denom if denom else 0.0


def hyper_at_least(N: int, K: int, n: int, k_min: int) -> float:
    return sum(hyper_pmf(N, K, n, k) for k in range(k_min, min(K, n) + 1))


def odds_string(p: float) -> str:
    if p <= 0:
        return "Impossível"
    if p >= 1:
        return "Certeza"
    odds = 1 / p
    if odds < 1_000:
        return f"1 em {odds:,.0f}"
    if odds < 1_000_000:
        return f"1 em {odds:,.0f}".replace(",", ".")
    if odds < 1_000_000_000:
        return f"1 em {odds / 1_000_000:.2f} milhões"
    return f"1 em {odds / 1_000_000_000:.2f} bilhões"


def coin_flip_equivalent(p: float) -> str:
    if p <= 0:
        return "—"
    flips = log2(1 / p)
    return f"≈ acertar {flips:.0f} cara-ou-coroa seguidos"


def calculate_prize_probabilities(config: LotteryConfig, n_picks: int) -> List[Dict[str, Any]]:
    lt = config.lottery_type
    results: List[Dict[str, Any]] = []

    if lt == LotteryType.LOTOMANIA:
        total = comb(100, 20)
        for tier in config.prize_tiers:
            k = tier.min_matches
            if k == 0:
                p = comb(50, 20) / total          # all 20 drawn from the OTHER 50
            else:
                p = comb(50, k) * comb(50, 20 - k) / total
            results.append(_row(tier, p))
        return results

    if lt == LotteryType.SUPER_SETE:
        for tier in config.prize_tiers:
            k = tier.min_matches
            p = sum(comb(7, j) * (0.1 ** j) * (0.9 ** (7 - j)) for j in range(k, 8))
            results.append(_row(tier, p))
        return results

    if lt == LotteryType.MAIS_MILIONARIA:
        N_num, draw_num = 50, 6
        N_trev, draw_trev, pick_trev = 6, 2, 2
        for tier in config.prize_tiers:
            p_num  = hyper_pmf(N_num,  n_picks,   draw_num,  tier.min_matches)
            p_trev = hyper_pmf(N_trev, pick_trev, draw_trev, tier.min_extra_matches)
            results.append(_row(tier, p_num * p_trev))
        return results

    if lt == LotteryType.TIMEMANIA:
        for tier in config.prize_tiers:
            if tier.min_extra_matches > 0:       # Time do Coração
                p = 1 / 80
            else:
                p = hyper_at_least(80, n_picks, 7, tier.min_matches)
            results.append(_row(tier, p))
        return results

    if lt == LotteryType.DIA_DE_SORTE:
        N = config.number_range[1] - config.number_range[0] + 1
        for tier in config.prize_tiers:
            if tier.min_extra_matches > 0:       # Mês de Sorte
                p = 1 / 12
            else:
                p = hyper_at_least(N, n_picks, config.draw_count, tier.min_matches)
            results.append(_row(tier, p))
        return results

    if lt == LotteryType.DUPLA_SENA:
        N = config.number_range[1] - config.number_range[0] + 1
        for tier in config.prize_tiers:
            p_one = hyper_at_least(N, n_picks, config.draw_count, tier.min_matches)
            p = 1 - (1 - p_one) ** 2            # win in at least one of two draws
            results.append(_row(tier, p))
        return results

    # Default: Mega-Sena, Quina, Lotofácil
    N = config.number_range[1] - config.number_range[0] + 1
    for tier in config.prize_tiers:
        p = hyper_at_least(N, n_picks, config.draw_count, tier.min_matches)
        results.append(_row(tier, p))
    return results


def overall_win_probability(config: LotteryConfig, n_picks: int) -> float:
    rows = calculate_prize_probabilities(config, n_picks)
    probs = [r["probability"] for r in rows]
    if not probs:
        return 0.0
    # P(win any prize) ≈ sum for independent tiers (approximation good enough for display)
    total = 0.0
    for p in probs:
        total = total + p - total * p   # inclusion-exclusion approximation
    return min(total, 1.0)


def _row(tier: PrizeTier, p: float) -> Dict[str, Any]:
    return {
        "tier": tier,
        "probability": p,
        "odds": odds_string(p),
        "percent": f"{p * 100:.6f}%",
        "coin_flips": coin_flip_equivalent(p),
    }
