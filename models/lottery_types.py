from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class LotteryType(Enum):
    MEGA_SENA      = "Mega-Sena"
    QUINA          = "Quina"
    LOTOFACIL      = "Lotofácil"
    LOTOMANIA      = "Lotomania"
    TIMEMANIA      = "Timemania"
    DUPLA_SENA     = "Dupla-Sena"
    DIA_DE_SORTE   = "Dia de Sorte"
    SUPER_SETE     = "Super Sete"
    MAIS_MILIONARIA = "+Milionária"


@dataclass
class PrizeTier:
    name: str
    min_matches: int
    min_extra_matches: int = 0
    prize_type: str = "variable"   # "jackpot" | "variable" | "fixed"
    fixed_value: float = 0.0
    pool_pct: float = 0.0


@dataclass
class LotteryConfig:
    lottery_type: LotteryType
    display_name: str
    emoji: str
    number_range: Tuple[int, int]   # inclusive
    min_picks: int
    max_picks: int
    draw_count: int
    ticket_price: float
    draw_days: str
    prize_tiers: List[PrizeTier]
    description: str = ""
    extra_name: Optional[str] = None   # "Trevo" | "Mês" | "Time"
    extra_range: Optional[Tuple[int, int]] = None
    extra_picks: int = 0
    extra_draw_count: int = 0
    fixed_picks: bool = False           # must pick exactly min_picks
    is_positional: bool = False         # Super Sete
    has_second_draw: bool = False       # Dupla-Sena


TIMEMANIA_TEAMS: dict[int, str] = {
    1: "ABC",            2: "América-MG",     3: "América-RN",    4: "ASA",
    5: "Atlético-GO",    6: "Atlético-MG",    7: "Avaí",          8: "Bahia",
    9: "Botafogo",      10: "Bragantino",     11: "Caldense",     12: "Caxias",
    13: "Ceará",        14: "Chapecoense",    15: "CRB",          16: "Criciúma",
    17: "Cruzeiro",     18: "CSA",            19: "Cuiabá",       20: "Figueirense",
    21: "Flamengo",     22: "Fluminense",     23: "Fortaleza",    24: "Goiás",
    25: "Grêmio",       26: "Guarani",        27: "Internacional", 28: "Ituano",
    29: "Joinville",    30: "Juventude",      31: "Náutico",      32: "Novo Hamburgo",
    33: "Oeste",        34: "Operário-PR",    35: "Palmeiras",    36: "Paraná",
    37: "Paysandu",     38: "Ponte Preta",    39: "Portuguesa",   40: "Remo",
    41: "Santos",       42: "São Paulo",      43: "Sport",        44: "Tombense",
    45: "Treze",        46: "Tupi",           47: "Vasco",        48: "Vila Nova",
    49: "Vitória",      50: "Volta Redonda",  51: "Altos",        52: "Araguaína",
    53: "Atlético-CE",  54: "Botafogo-PB",    55: "Campinense",   56: "Corinthians",
    57: "Ferroviário",  58: "Ferroviária",    59: "Floresta",     60: "Galvez",
    61: "Globo",        62: "Imperatriz",     63: "Independente", 64: "Lagarto",
    65: "Moto Club",    66: "Murici",         67: "River-PI",     68: "Sampaio Corrêa",
    69: "São Raimundo", 70: "Serra",          71: "Sousa",        72: "Brasil de Pelotas",
    73: "Luverdense",   74: "Recife",         75: "Porto Alegre", 76: "Barra",
    77: "ABC-MT",       78: "Barcelona-EC",   79: "Atlético-AC",  80: "Pafos",
}

DIA_DE_SORTE_MONTHS: dict[int, str] = {
    1: "Janeiro",   2: "Fevereiro",  3: "Março",    4: "Abril",
    5: "Maio",      6: "Junho",      7: "Julho",    8: "Agosto",
    9: "Setembro", 10: "Outubro",   11: "Novembro", 12: "Dezembro",
}

LOTTERY_CONFIGS: dict[LotteryType, LotteryConfig] = {

    LotteryType.MEGA_SENA: LotteryConfig(
        lottery_type=LotteryType.MEGA_SENA,
        display_name="Mega-Sena",
        emoji="🍀",
        number_range=(1, 60),
        min_picks=6,
        max_picks=20,
        draw_count=6,
        ticket_price=5.00,
        draw_days="Quarta-feira e Sábado (20h)",
        description="Acerte 6 números de 60. Mínimo 4 acertos para ganhar.",
        prize_tiers=[
            PrizeTier("Sena (6 acertos)",   6, prize_type="jackpot",  pool_pct=35.0),
            PrizeTier("Quina (5 acertos)",  5, prize_type="variable", pool_pct=19.0),
            PrizeTier("Quadra (4 acertos)", 4, prize_type="variable", pool_pct=19.0),
        ],
    ),

    LotteryType.QUINA: LotteryConfig(
        lottery_type=LotteryType.QUINA,
        display_name="Quina",
        emoji="5️⃣",
        number_range=(1, 80),
        min_picks=5,
        max_picks=15,
        draw_count=5,
        ticket_price=2.50,
        draw_days="Segunda a Sábado (20h)",
        description="Acerte 5 números de 80. Premia a partir de 2 acertos!",
        prize_tiers=[
            PrizeTier("Quina (5 acertos)",  5, prize_type="jackpot",  pool_pct=28.0),
            PrizeTier("Quadra (4 acertos)", 4, prize_type="variable", pool_pct=15.0),
            PrizeTier("Terno (3 acertos)",  3, prize_type="variable", pool_pct=15.0),
            PrizeTier("Duque (2 acertos)",  2, prize_type="variable", pool_pct=15.0),
        ],
    ),

    LotteryType.LOTOFACIL: LotteryConfig(
        lottery_type=LotteryType.LOTOFACIL,
        display_name="Lotofácil",
        emoji="🎯",
        number_range=(1, 25),
        min_picks=15,
        max_picks=20,
        draw_count=15,
        ticket_price=3.00,
        draw_days="Segunda, Quarta e Sexta (20h)",
        description="Acerte 15 números de 25. A loteria mais fácil de ganhar!",
        prize_tiers=[
            PrizeTier("15 acertos", 15, prize_type="jackpot",  pool_pct=35.0),
            PrizeTier("14 acertos", 14, prize_type="variable", pool_pct=20.0),
            PrizeTier("13 acertos", 13, prize_type="fixed",    fixed_value=25.0),
            PrizeTier("12 acertos", 12, prize_type="fixed",    fixed_value=10.0),
            PrizeTier("11 acertos", 11, prize_type="fixed",    fixed_value=5.0),
        ],
    ),

    LotteryType.LOTOMANIA: LotteryConfig(
        lottery_type=LotteryType.LOTOMANIA,
        display_name="Lotomania",
        emoji="🎲",
        number_range=(1, 100),
        min_picks=50,
        max_picks=50,
        draw_count=20,
        ticket_price=3.00,
        draw_days="Terça-feira e Sexta-feira (20h)",
        fixed_picks=True,
        description="Marque EXATAMENTE 50 números de 100. Ganha com 0 ou de 15 a 20 acertos!",
        prize_tiers=[
            PrizeTier("20 acertos", 20, prize_type="jackpot",  pool_pct=45.0),
            PrizeTier("19 acertos", 19, prize_type="variable", pool_pct=16.0),
            PrizeTier("18 acertos", 18, prize_type="variable", pool_pct=10.0),
            PrizeTier("17 acertos", 17, prize_type="variable", pool_pct=7.0),
            PrizeTier("16 acertos", 16, prize_type="variable", pool_pct=7.0),
            PrizeTier("15 acertos", 15, prize_type="variable", pool_pct=7.0),
            PrizeTier("0 acertos",   0, prize_type="variable", pool_pct=8.0),
        ],
    ),

    LotteryType.TIMEMANIA: LotteryConfig(
        lottery_type=LotteryType.TIMEMANIA,
        display_name="Timemania",
        emoji="⚽",
        number_range=(1, 80),
        min_picks=10,
        max_picks=10,
        draw_count=7,
        ticket_price=4.50,
        draw_days="Terça-feira, Quinta-feira e Sábado (20h)",
        fixed_picks=True,
        extra_name="Time do Coração",
        extra_range=(1, 80),
        extra_picks=1,
        extra_draw_count=1,
        description="Escolha 10 números de 80 + 1 time. Sorteiam-se 7 números + 1 time.",
        prize_tiers=[
            PrizeTier("7 acertos",          7, prize_type="jackpot",  pool_pct=33.0),
            PrizeTier("6 acertos",          6, prize_type="variable", pool_pct=15.0),
            PrizeTier("5 acertos",          5, prize_type="variable", pool_pct=15.0),
            PrizeTier("4 acertos",          4, prize_type="variable", pool_pct=15.0),
            PrizeTier("3 acertos",          3, prize_type="variable", pool_pct=15.0),
            PrizeTier("Time do Coração",    0, min_extra_matches=1, prize_type="variable", pool_pct=7.0),
        ],
    ),

    LotteryType.DUPLA_SENA: LotteryConfig(
        lottery_type=LotteryType.DUPLA_SENA,
        display_name="Dupla-Sena",
        emoji="🎰",
        number_range=(1, 50),
        min_picks=6,
        max_picks=15,
        draw_count=6,
        ticket_price=4.00,
        draw_days="Segunda-feira, Quarta-feira e Sexta-feira (20h)",
        has_second_draw=True,
        description="6 números de 50. DOIS sorteios por concurso! Dobro de chances de ganhar.",
        prize_tiers=[
            PrizeTier("Sena (6 acertos)",   6, prize_type="jackpot",  pool_pct=25.0),
            PrizeTier("Quina (5 acertos)",  5, prize_type="variable", pool_pct=15.0),
            PrizeTier("Quadra (4 acertos)", 4, prize_type="variable", pool_pct=15.0),
            PrizeTier("Terno (3 acertos)",  3, prize_type="variable", pool_pct=15.0),
        ],
    ),

    LotteryType.DIA_DE_SORTE: LotteryConfig(
        lottery_type=LotteryType.DIA_DE_SORTE,
        display_name="Dia de Sorte",
        emoji="☀️",
        number_range=(1, 31),
        min_picks=7,
        max_picks=15,
        draw_count=7,
        ticket_price=3.00,
        draw_days="Terça-feira, Quinta-feira e Sábado (20h)",
        extra_name="Mês de Sorte",
        extra_range=(1, 12),
        extra_picks=1,
        extra_draw_count=1,
        description="7 números de 31 + 1 Mês de Sorte. Acerte o mês e ganhe um prêmio extra!",
        prize_tiers=[
            PrizeTier("7 acertos",      7, prize_type="jackpot",  pool_pct=40.0),
            PrizeTier("6 acertos",      6, prize_type="variable", pool_pct=20.0),
            PrizeTier("5 acertos",      5, prize_type="variable", pool_pct=15.0),
            PrizeTier("4 acertos",      4, prize_type="variable", pool_pct=15.0),
            PrizeTier("Mês de Sorte",   0, min_extra_matches=1, prize_type="fixed", fixed_value=2.0),
        ],
    ),

    LotteryType.SUPER_SETE: LotteryConfig(
        lottery_type=LotteryType.SUPER_SETE,
        display_name="Super Sete",
        emoji="7️⃣",
        number_range=(0, 9),
        min_picks=7,
        max_picks=7,
        draw_count=7,
        ticket_price=2.50,
        draw_days="Segunda-feira, Quarta-feira e Sexta-feira (20h)",
        fixed_picks=True,
        is_positional=True,
        description="1 dígito (0–9) por coluna, 7 colunas. Acertos são POSICIONAIS!",
        prize_tiers=[
            PrizeTier("7 colunas", 7, prize_type="jackpot",  pool_pct=35.0),
            PrizeTier("6 colunas", 6, prize_type="variable", pool_pct=20.0),
            PrizeTier("5 colunas", 5, prize_type="variable", pool_pct=15.0),
            PrizeTier("4 colunas", 4, prize_type="variable", pool_pct=15.0),
            PrizeTier("3 colunas", 3, prize_type="fixed",    fixed_value=5.0),
        ],
    ),

    LotteryType.MAIS_MILIONARIA: LotteryConfig(
        lottery_type=LotteryType.MAIS_MILIONARIA,
        display_name="+Milionária",
        emoji="💎",
        number_range=(1, 50),
        min_picks=6,
        max_picks=12,
        draw_count=6,
        ticket_price=6.00,
        draw_days="Quarta-feira e Sábado (22h)",
        extra_name="Trevos",
        extra_range=(1, 6),
        extra_picks=2,
        extra_draw_count=2,
        description="6 números de 50 + 2 trevos de 6. 10 faixas de prêmio!",
        prize_tiers=[
            PrizeTier("6 números + 2 trevos", 6, min_extra_matches=2, prize_type="jackpot",  pool_pct=40.0),
            PrizeTier("6 números + 1 trevo",  6, min_extra_matches=1, prize_type="variable", pool_pct=10.0),
            PrizeTier("5 números + 2 trevos", 5, min_extra_matches=2, prize_type="variable", pool_pct=8.0),
            PrizeTier("5 números + 1 trevo",  5, min_extra_matches=1, prize_type="variable", pool_pct=8.0),
            PrizeTier("4 números + 2 trevos", 4, min_extra_matches=2, prize_type="variable", pool_pct=6.0),
            PrizeTier("4 números + 1 trevo",  4, min_extra_matches=1, prize_type="variable", pool_pct=6.0),
            PrizeTier("3 números + 2 trevos", 3, min_extra_matches=2, prize_type="fixed",    fixed_value=50.0),
            PrizeTier("3 números + 1 trevo",  3, min_extra_matches=1, prize_type="fixed",    fixed_value=24.0),
            PrizeTier("2 números + 2 trevos", 2, min_extra_matches=2, prize_type="fixed",    fixed_value=12.0),
            PrizeTier("2 números + 1 trevo",  2, min_extra_matches=1, prize_type="fixed",    fixed_value=6.0),
        ],
    ),
}
