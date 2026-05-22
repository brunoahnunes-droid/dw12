"""Terminal UI for the Brazilian lottery checker."""
import sys
from typing import List, Optional

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule

from models.lottery_types import (
    LotteryType, LotteryConfig, LOTTERY_CONFIGS,
    TIMEMANIA_TEAMS, DIA_DE_SORTE_MONTHS,
)
from models.ticket import Ticket, DrawResult
import os
from services.checker import check_ticket, CheckResult
from services.probability import (
    calculate_prize_probabilities, overall_win_probability, odds_string,
)
from services.generator import generate_games
from services.excel_export import export_generated_games, export_check_results
from storage.store import Store

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "exports")

console = Console()

PRIZE_COLORS = {
    "jackpot":  "bold gold1",
    "variable": "bold cyan",
    "fixed":    "bold green",
}

TIER_EMOJI = {
    "jackpot":  "🏆",
    "variable": "🥈",
    "fixed":    "💵",
}


# ─────────────────────────── helpers ────────────────────────────────────────

def _banner():
    console.print()
    console.print(Panel.fit(
        "[bold yellow]🎰  CONFERIDOR DE LOTERIAS CAIXA  🎰[/bold yellow]\n"
        "[dim]Mega-Sena · Quina · Lotofácil · Lotomania · Timemania\n"
        "Dupla-Sena · Dia de Sorte · Super Sete · +Milionária[/dim]",
        border_style="yellow",
    ))
    console.print()


def _choose_lottery() -> LotteryType:
    choices = []
    for lt, cfg in LOTTERY_CONFIGS.items():
        choices.append(questionary.Choice(
            title=f"{cfg.emoji}  {cfg.display_name}",
            value=lt,
        ))
    return questionary.select(
        "Selecione o tipo de jogo:",
        choices=choices,
        style=_qs(),
    ).ask()


def _qs():
    return questionary.Style([
        ("qmark",        "fg:#FFD700 bold"),
        ("question",     "bold"),
        ("answer",       "fg:#00BFFF bold"),
        ("pointer",      "fg:#FFD700 bold"),
        ("highlighted",  "fg:#FFD700 bold"),
        ("selected",     "fg:#00FF7F"),
    ])


def _show_config(cfg: LotteryConfig):
    console.print(Panel(
        f"[bold]{cfg.emoji} {cfg.display_name}[/bold]\n\n"
        f"[dim]{cfg.description}[/dim]\n\n"
        f"[cyan]Intervalo:[/cyan] {cfg.number_range[0]}–{cfg.number_range[1]}   "
        f"[cyan]Escolhas:[/cyan] {cfg.min_picks}"
        + (f"–{cfg.max_picks}" if cfg.max_picks != cfg.min_picks else "") +
        f"   [cyan]Sorteio:[/cyan] {cfg.draw_count} números\n"
        f"[cyan]Preço base:[/cyan] R$ {cfg.ticket_price:.2f}   "
        f"[cyan]Sorteios:[/cyan] {cfg.draw_days}",
        title="Informações do Jogo",
        border_style="cyan",
    ))


def _fmt_numbers(numbers: List[int], highlight: set | None = None,
                 positional_ok: List[int] | None = None,
                 width: int = 3) -> Text:
    t = Text()
    for i, n in enumerate(numbers):
        tag = str(n).zfill(width)
        if positional_ok is not None:
            ok = i < len(positional_ok) and positional_ok[i] == n
            style = "bold green" if ok else "dim red"
        elif highlight and n in highlight:
            style = "bold green"
        else:
            style = "dim"
        t.append(f" {tag}", style=style)
    return t


def _parse_numbers(raw: str, lo: int, hi: int, count: int | None,
                   label: str = "número") -> Optional[List[int]]:
    parts = raw.replace(",", " ").split()
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        console.print(f"[red]Entrada inválida. Use apenas números separados por espaço.[/red]")
        return None
    invalids = [n for n in nums if not (lo <= n <= hi)]
    if invalids:
        console.print(f"[red]Números fora do intervalo {lo}–{hi}: {invalids}[/red]")
        return None
    if count and len(nums) != count:
        console.print(f"[red]Informe exatamente {count} {label}(s). Você digitou {len(nums)}.[/red]")
        return None
    if len(nums) != len(set(nums)):
        console.print(f"[red]Números repetidos não são permitidos.[/red]")
        return None
    return nums


# ─────────────────────────── add ticket ─────────────────────────────────────

def _add_ticket(store: Store):
    console.print(Rule("[bold yellow]Adicionar Jogo[/bold yellow]"))
    lt = _choose_lottery()
    if lt is None:
        return
    cfg = LOTTERY_CONFIGS[lt]
    _show_config(cfg)

    # Main numbers
    if cfg.fixed_picks:
        prompt = (f"Digite os {cfg.min_picks} números "
                  f"({cfg.number_range[0]}–{cfg.number_range[1]})")
        required = cfg.min_picks
    else:
        prompt = (f"Digite os números "
                  f"({cfg.min_picks}–{cfg.max_picks} números, "
                  f"intervalo {cfg.number_range[0]}–{cfg.number_range[1]})")
        required = None

    while True:
        raw = questionary.text(prompt + ":", style=_qs()).ask()
        if raw is None:
            return
        lo, hi = cfg.number_range
        nums = _parse_numbers(raw, lo, hi, required)
        if nums is None:
            continue
        if required is None and not (cfg.min_picks <= len(nums) <= cfg.max_picks):
            console.print(f"[red]Informe entre {cfg.min_picks} e {cfg.max_picks} números.[/red]")
            continue
        break

    extra = None

    # Timemania team
    if lt == LotteryType.TIMEMANIA:
        console.print("\n[cyan]Times disponíveis:[/cyan]")
        teams_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        teams_table.add_column(style="dim")
        teams_table.add_column()
        teams_table.add_column(style="dim")
        teams_table.add_column()
        items = list(TIMEMANIA_TEAMS.items())
        for i in range(0, len(items), 2):
            row = [str(items[i][0]), items[i][1]]
            if i + 1 < len(items):
                row += [str(items[i+1][0]), items[i+1][1]]
            else:
                row += ["", ""]
            teams_table.add_row(*row)
        console.print(teams_table)
        while True:
            raw = questionary.text("Número do Time do Coração (1–80):", style=_qs()).ask()
            if raw is None:
                return
            try:
                team = int(raw.strip())
                if 1 <= team <= 80:
                    extra = team
                    console.print(f"[green]Time: {TIMEMANIA_TEAMS.get(team, str(team))}[/green]")
                    break
            except ValueError:
                pass
            console.print("[red]Número inválido. Digite entre 1 e 80.[/red]")

    # Dia de Sorte month
    elif lt == LotteryType.DIA_DE_SORTE:
        month_choices = [
            questionary.Choice(title=f"{k:02d} – {v}", value=k)
            for k, v in DIA_DE_SORTE_MONTHS.items()
        ]
        extra = questionary.select("Mês de Sorte:", choices=month_choices, style=_qs()).ask()
        if extra is None:
            return

    # +Milionária trevos
    elif lt == LotteryType.MAIS_MILIONARIA:
        while True:
            raw = questionary.text("Digite 2 Trevos (1–6), ex: 3 5:", style=_qs()).ask()
            if raw is None:
                return
            trevos = _parse_numbers(raw, 1, 6, 2, "trevo")
            if trevos:
                extra = sorted(trevos)
                break

    label = questionary.text("Rótulo opcional (Enter para pular):", style=_qs()).ask() or ""

    ticket = Ticket.create(lt, nums, extra=extra, label=label)
    store.add_ticket(ticket)

    console.print(f"\n[bold green]✅ Jogo adicionado! ID: [yellow]{ticket.id}[/yellow][/bold green]")
    _print_ticket_summary(ticket, cfg)


def _print_ticket_summary(ticket: Ticket, cfg: LotteryConfig):
    t = Text()
    t.append(f"\n  {cfg.emoji} {cfg.display_name}  ")
    t.append("  ".join(str(n).zfill(2) for n in ticket.numbers), style="bold cyan")
    if ticket.extra is not None:
        if cfg.lottery_type == LotteryType.TIMEMANIA:
            t.append(f"  ⚽ {TIMEMANIA_TEAMS.get(ticket.extra, ticket.extra)}", style="yellow")
        elif cfg.lottery_type == LotteryType.DIA_DE_SORTE:
            t.append(f"  ☀️ {DIA_DE_SORTE_MONTHS.get(ticket.extra, ticket.extra)}", style="yellow")
        elif cfg.lottery_type == LotteryType.MAIS_MILIONARIA:
            t.append(f"  💎 Trevos: {ticket.extra}", style="yellow")
    if ticket.label:
        t.append(f"  [{ticket.label}]", style="dim")
    console.print(Panel(t, border_style="green"))


# ─────────────────────────── list tickets ───────────────────────────────────

def _list_tickets(store: Store):
    console.print(Rule("[bold yellow]Meus Jogos[/bold yellow]"))

    # Filter choice
    show_all = questionary.confirm(
        "Mostrar todos os tipos de jogo?", default=True, style=_qs()
    ).ask()
    if show_all is None:
        return

    if show_all:
        tickets = store.get_tickets()
    else:
        lt = _choose_lottery()
        if lt is None:
            return
        tickets = store.get_tickets(lt)

    if not tickets:
        console.print("[yellow]Nenhum jogo cadastrado.[/yellow]")
        return

    table = Table(title=f"Total: {len(tickets)} jogo(s)", box=box.ROUNDED,
                  border_style="cyan", show_lines=True)
    table.add_column("ID",      style="yellow", no_wrap=True)
    table.add_column("Jogo",    style="bold")
    table.add_column("Números", style="cyan")
    table.add_column("Extra",   style="magenta")
    table.add_column("Rótulo",  style="dim")
    table.add_column("Data",    style="dim")

    for t in tickets:
        cfg = LOTTERY_CONFIGS[t.lottery_type]
        nums_str = "  ".join(str(n).zfill(2) for n in t.numbers)
        extra_str = _extra_display(t, cfg)
        table.add_row(t.id, f"{cfg.emoji} {cfg.display_name}",
                      nums_str, extra_str, t.label, t.created_at)

    console.print(table)


def _extra_display(ticket: Ticket, cfg: LotteryConfig) -> str:
    if ticket.extra is None:
        return "—"
    if cfg.lottery_type == LotteryType.TIMEMANIA:
        return f"⚽ {TIMEMANIA_TEAMS.get(ticket.extra, ticket.extra)}"
    if cfg.lottery_type == LotteryType.DIA_DE_SORTE:
        return f"☀️ {DIA_DE_SORTE_MONTHS.get(ticket.extra, ticket.extra)}"
    if cfg.lottery_type == LotteryType.MAIS_MILIONARIA:
        return f"💎 {ticket.extra}"
    return str(ticket.extra)


# ─────────────────────────── remove ticket ──────────────────────────────────

def _remove_ticket(store: Store):
    console.print(Rule("[bold yellow]Remover Jogo[/bold yellow]"))
    tickets = store.get_tickets()
    if not tickets:
        console.print("[yellow]Nenhum jogo para remover.[/yellow]")
        return

    choices = []
    for t in tickets:
        cfg = LOTTERY_CONFIGS[t.lottery_type]
        nums = "  ".join(str(n).zfill(2) for n in t.numbers[:6])
        if len(t.numbers) > 6:
            nums += " ..."
        label = f" [{t.label}]" if t.label else ""
        choices.append(questionary.Choice(
            title=f"[{t.id}] {cfg.emoji} {cfg.display_name}  {nums}{label}",
            value=t.id,
        ))
    choices.append(questionary.Choice(title="← Voltar", value=None))

    tid = questionary.select("Selecione o jogo a remover:", choices=choices, style=_qs()).ask()
    if not tid:
        return
    if questionary.confirm(f"Remover jogo {tid}?", style=_qs()).ask():
        store.remove_ticket(tid)
        console.print(f"[green]Jogo {tid} removido.[/green]")


# ─────────────────────────── check draw ─────────────────────────────────────

def _check_draw(store: Store):
    console.print(Rule("[bold yellow]Conferir Sorteio[/bold yellow]"))
    lt = _choose_lottery()
    if lt is None:
        return
    cfg = LOTTERY_CONFIGS[lt]

    tickets = store.get_tickets(lt)
    if not tickets:
        console.print(f"[yellow]Nenhum jogo cadastrado para {cfg.display_name}.[/yellow]")
        return

    console.print(f"\n[bold]Você tem {len(tickets)} jogo(s) de {cfg.emoji} {cfg.display_name}[/bold]")
    contest = questionary.text("Número do concurso (opcional):", style=_qs()).ask() or ""
    date    = questionary.text("Data do sorteio (opcional):",    style=_qs()).ask() or ""

    # Draw numbers
    draw_numbers = _input_draw_numbers(cfg, "1º sorteio")
    if draw_numbers is None:
        return

    draw_numbers2 = None
    if cfg.has_second_draw:
        draw_numbers2 = _input_draw_numbers(cfg, "2º sorteio (Dupla-Sena)")
        if draw_numbers2 is None:
            return

    draw_extra = _input_draw_extra(cfg)

    draw = DrawResult(
        lottery_type=lt,
        numbers=draw_numbers,
        numbers2=draw_numbers2,
        extra=draw_extra,
        contest_number=contest,
        draw_date=date,
    )

    # Run check
    results: List[CheckResult] = [check_ticket(t, draw) for t in tickets]
    winners = [r for r in results if r.is_winner]

    _print_draw_header(cfg, draw)
    _print_check_results(results, cfg)
    _print_financial_summary(results, cfg)

    if questionary.confirm("Salvar este sorteio no histórico?", default=True, style=_qs()).ask():
        store.save_draw(draw)
        console.print("[green]Sorteio salvo.[/green]")

    if questionary.confirm("Exportar resultado para Excel?", default=True, style=_qs()).ask():
        path = export_check_results(results, draw, EXPORTS_DIR, cfg.ticket_price)
        console.print(f"[bold green]✅ Excel salvo em:[/bold green] [cyan]{path}[/cyan]")


def _input_draw_numbers(cfg: LotteryConfig, label: str) -> Optional[List[int]]:
    lo, hi = cfg.number_range
    while True:
        raw = questionary.text(
            f"Números do {label} ({cfg.draw_count} números, {lo}–{hi}):",
            style=_qs(),
        ).ask()
        if raw is None:
            return None
        nums = _parse_numbers(raw, lo, hi, cfg.draw_count)
        if nums:
            return nums


def _input_draw_extra(cfg: LotteryConfig) -> Optional[object]:
    lt = cfg.lottery_type
    if lt == LotteryType.TIMEMANIA:
        while True:
            raw = questionary.text("Time do Coração sorteado (número 1–80):", style=_qs()).ask()
            if raw is None:
                return None
            try:
                t = int(raw.strip())
                if 1 <= t <= 80:
                    return t
            except ValueError:
                pass
            console.print("[red]Inválido.[/red]")

    if lt == LotteryType.DIA_DE_SORTE:
        month_choices = [
            questionary.Choice(title=f"{k:02d} – {v}", value=k)
            for k, v in DIA_DE_SORTE_MONTHS.items()
        ]
        return questionary.select("Mês de Sorte sorteado:", choices=month_choices, style=_qs()).ask()

    if lt == LotteryType.MAIS_MILIONARIA:
        while True:
            raw = questionary.text("Trevos sorteados (2 números 1–6):", style=_qs()).ask()
            if raw is None:
                return None
            trevos = _parse_numbers(raw, 1, 6, 2, "trevo")
            if trevos:
                return sorted(trevos)

    return None


def _print_draw_header(cfg: LotteryConfig, draw: DrawResult):
    console.print()
    title = f"{cfg.emoji}  {cfg.display_name}"
    if draw.contest_number:
        title += f"  –  Concurso {draw.contest_number}"
    if draw.draw_date:
        title += f"  ({draw.draw_date})"

    nums_text = "  ".join(f"[bold yellow]{n:02d}[/bold yellow]" for n in sorted(draw.numbers))
    body = f"Números sorteados:  {nums_text}"

    if draw.numbers2:
        nums2_text = "  ".join(f"[bold yellow]{n:02d}[/bold yellow]" for n in sorted(draw.numbers2))
        body += f"\n2º sorteio:         {nums2_text}"

    if draw.extra is not None:
        if cfg.lottery_type == LotteryType.TIMEMANIA:
            body += f"\n⚽ Time: [bold yellow]{TIMEMANIA_TEAMS.get(draw.extra, draw.extra)}[/bold yellow]"
        elif cfg.lottery_type == LotteryType.DIA_DE_SORTE:
            body += f"\n☀️ Mês: [bold yellow]{DIA_DE_SORTE_MONTHS.get(draw.extra, draw.extra)}[/bold yellow]"
        elif cfg.lottery_type == LotteryType.MAIS_MILIONARIA:
            body += f"\n💎 Trevos: [bold yellow]{draw.extra}[/bold yellow]"

    console.print(Panel(body, title=title, border_style="yellow"))


def _print_check_results(results: List[CheckResult], cfg: LotteryConfig):
    table = Table(
        title=f"Conferência de {len(results)} jogo(s)",
        box=box.ROUNDED, border_style="blue", show_lines=True,
    )
    table.add_column("ID",       style="yellow", no_wrap=True)
    table.add_column("Rótulo",   style="dim")
    table.add_column("Seus Números", no_wrap=True)
    table.add_column("Acertos",  justify="center")

    if cfg.has_second_draw:
        table.add_column("Acertos 2º", justify="center")

    if cfg.extra_name:
        table.add_column(cfg.extra_name, justify="center")

    table.add_column("Prêmio", style="bold")

    for r in results:
        # Build highlighted number string
        if cfg.is_positional:
            draw_set = None
            pos_ok = r.draw.numbers
        else:
            draw_set = set(r.draw.numbers)
            pos_ok = None

        nums_text = _fmt_numbers(r.ticket.numbers, draw_set, pos_ok)
        acertos_str = _acertos_badge(r.matches, r.prize_tier is not None)

        row = [r.ticket.id, r.ticket.label, nums_text, acertos_str]

        if cfg.has_second_draw:
            row.append(_acertos_badge(r.matches2, r.prize_tier2 is not None))

        if cfg.extra_name:
            row.append(_extra_match_badge(r, cfg))

        row.append(_prize_badge(r.best_prize))
        table.add_row(*row)

    console.print(table)


def _acertos_badge(matches: int, won: bool) -> str:
    color = "bold green" if won else ("yellow" if matches > 0 else "dim")
    return f"[{color}]{matches}[/{color}]"


def _extra_match_badge(r: CheckResult, cfg: LotteryConfig) -> str:
    if r.extra_matches:
        if cfg.lottery_type == LotteryType.TIMEMANIA:
            return f"[green]✅ {TIMEMANIA_TEAMS.get(r.ticket.extra, r.ticket.extra)}[/green]"
        if cfg.lottery_type == LotteryType.DIA_DE_SORTE:
            return f"[green]✅ {DIA_DE_SORTE_MONTHS.get(r.ticket.extra, r.ticket.extra)}[/green]"
        if cfg.lottery_type == LotteryType.MAIS_MILIONARIA:
            return f"[green]✅ {r.extra_matches} trevo(s)[/green]"
    if r.ticket.extra is None:
        return "—"
    if cfg.lottery_type == LotteryType.TIMEMANIA:
        return f"[dim]❌ {TIMEMANIA_TEAMS.get(r.ticket.extra, r.ticket.extra)}[/dim]"
    if cfg.lottery_type == LotteryType.DIA_DE_SORTE:
        return f"[dim]❌ {DIA_DE_SORTE_MONTHS.get(r.ticket.extra, r.ticket.extra)}[/dim]"
    if cfg.lottery_type == LotteryType.MAIS_MILIONARIA:
        return f"[dim]❌ 0 trevo(s)[/dim]"
    return "—"


def _prize_badge(tier) -> str:
    if tier is None:
        return "[dim]Sem prêmio[/dim]"
    emoji = TIER_EMOJI.get(tier.prize_type, "🎁")
    color = PRIZE_COLORS.get(tier.prize_type, "bold white")
    label = tier.name
    if tier.prize_type == "fixed":
        label += f" (R$ {tier.fixed_value:.2f})"
    return f"[{color}]{emoji} {label}[/{color}]"


def _print_financial_summary(results: List[CheckResult], cfg: LotteryConfig):
    total      = len(results)
    winners    = [r for r in results if r.is_winner]
    n_win      = len(winners)
    color      = "green" if n_win else "red"

    total_spent = total * cfg.ticket_price
    fixed_ret   = 0.0
    var_prizes  = []

    for r in winners:
        for prize in [r.prize_tier, r.prize_tier2]:
            if prize is None:
                continue
            if prize.prize_type == "fixed":
                fixed_ret += prize.fixed_value
            elif prize.prize_type in ("variable", "jackpot"):
                if prize.name not in var_prizes:
                    var_prizes.append(prize.name)

    net       = fixed_ret - total_spent
    roi       = (fixed_ret / total_spent * 100) if total_spent else 0
    net_color = "green" if net >= 0 else "red"

    lines = (
        f"[bold]Jogos conferidos:[/bold]    {total}\n"
        f"[bold]Premiados:[/bold]           [{color}]{n_win}[/{color}]   "
        f"[dim]Sem prêmio: {total - n_win}[/dim]\n"
        f"\n"
        f"[bold]💰 Total investido:[/bold]  [red]R$ {total_spent:.2f}[/red]\n"
        f"[bold]🏆 Retorno fixo:[/bold]     [green]R$ {fixed_ret:.2f}[/green]\n"
        f"[bold]📊 Saldo líquido:[/bold]    [{net_color}]R$ {net:+.2f}[/{net_color}]   "
        f"ROI: [{net_color}]{roi:.1f}%[/{net_color}]"
    )
    if var_prizes:
        lines += f"\n[bold]⚠  Prêmios variáveis:[/bold] [yellow]{' | '.join(var_prizes)}[/yellow] [dim](consulte a Caixa)[/dim]"

    console.print()
    console.print(Panel(lines, title="📊 Resumo Financeiro", border_style=color))


# ─────────────────────────── generate games ──────────────────────────────────

def _generate_games(store: Store):
    console.print(Rule("[bold yellow]Gerador de Jogos[/bold yellow]"))
    lt = _choose_lottery()
    if lt is None:
        return
    cfg = LOTTERY_CONFIGS[lt]
    _show_config(cfg)

    # Number of picks per game
    if cfg.fixed_picks or cfg.is_positional:
        n_picks = cfg.min_picks
        console.print(f"\n[dim]Apostas fixas: {n_picks} números por jogo[/dim]")
    else:
        while True:
            raw = questionary.text(
                f"Quantos números por jogo? ({cfg.min_picks}–{cfg.max_picks}):",
                default=str(cfg.min_picks),
                style=_qs(),
            ).ask()
            if raw is None:
                return
            try:
                n_picks = int(raw.strip())
                if cfg.min_picks <= n_picks <= cfg.max_picks:
                    break
            except ValueError:
                pass
            console.print(f"[red]Digite entre {cfg.min_picks} e {cfg.max_picks}.[/red]")

    # Number of games
    while True:
        raw = questionary.text(
            "Quantos jogos gerar? (1–200):",
            default="10",
            style=_qs(),
        ).ask()
        if raw is None:
            return
        try:
            n_games = int(raw.strip())
            if 1 <= n_games <= 200:
                break
        except ValueError:
            pass
        console.print("[red]Digite um número entre 1 e 200.[/red]")

    # Cost preview
    total_cost = n_games * cfg.ticket_price
    console.print(
        f"\n[bold]Resumo:[/bold] {n_games} jogos × R$ {cfg.ticket_price:.2f} = "
        f"[bold red]R$ {total_cost:.2f}[/bold red]"
    )
    if not questionary.confirm("Gerar e salvar os jogos?", default=True, style=_qs()).ask():
        return

    # Generate
    tickets = generate_games(lt, n_picks, n_games)
    for t in tickets:
        store.add_ticket(t)

    console.print(f"\n[bold green]✅ {n_games} jogos gerados e salvos![/bold green]")

    # Preview table
    preview = Table(title=f"Prévia – primeiros {min(5, n_games)} jogos",
                    box=box.ROUNDED, border_style="cyan", show_lines=True)
    preview.add_column("ID",      style="yellow")
    preview.add_column("Números", style="cyan")
    if cfg.extra_name:
        preview.add_column(cfg.extra_name, style="magenta")

    for t in tickets[:5]:
        nums = "  ".join(str(n).zfill(2) for n in t.numbers)
        row = [t.id, nums]
        if cfg.extra_name:
            row.append(_extra_display(t, cfg))
        preview.add_row(*row)

    if n_games > 5:
        preview.add_row("[dim]...[/dim]", f"[dim]+ {n_games - 5} jogos[/dim]",
                        *([""]*( 1 if cfg.extra_name else 0)))
    console.print(preview)

    # Export to Excel
    if questionary.confirm("Exportar jogos para Excel?", default=True, style=_qs()).ask():
        path = export_generated_games(tickets, EXPORTS_DIR)
        console.print(f"[bold green]✅ Excel salvo em:[/bold green] [cyan]{path}[/cyan]")
        console.print("[dim]💡 Guarde o arquivo. Após o sorteio, use 'Conferir sorteio' "
                      "para verificar e exportar o resultado automaticamente.[/dim]")


# ─────────────────────────── probability ────────────────────────────────────

def _show_probability(store: Store):
    console.print(Rule("[bold yellow]Probabilidades de Ganhar[/bold yellow]"))
    lt = _choose_lottery()
    if lt is None:
        return
    cfg = LOTTERY_CONFIGS[lt]
    _show_config(cfg)

    # Pick size
    if cfg.fixed_picks:
        n_picks = cfg.min_picks
        console.print(f"\n[dim]Apostas fixas: {n_picks} números[/dim]")
    else:
        while True:
            raw = questionary.text(
                f"Quantos números na aposta? ({cfg.min_picks}–{cfg.max_picks}):",
                default=str(cfg.min_picks),
                style=_qs(),
            ).ask()
            if raw is None:
                return
            try:
                n_picks = int(raw.strip())
                if cfg.min_picks <= n_picks <= cfg.max_picks:
                    break
            except ValueError:
                pass
            console.print(f"[red]Digite entre {cfg.min_picks} e {cfg.max_picks}.[/red]")

    rows = calculate_prize_probabilities(cfg, n_picks)
    overall = overall_win_probability(cfg, n_picks)

    table = Table(
        title=f"{cfg.emoji} {cfg.display_name} – Probabilidades com {n_picks} número(s)",
        box=box.ROUNDED, border_style="magenta", show_lines=True,
    )
    table.add_column("Faixa de Prêmio",    style="bold", min_width=22)
    table.add_column("Probabilidade",       justify="right", style="cyan")
    table.add_column("Odds",                justify="right")
    table.add_column("Comparação",          style="dim", min_width=35)
    table.add_column("Tipo",               justify="center")

    for row in rows:
        tier = row["tier"]
        color = PRIZE_COLORS.get(tier.prize_type, "white")
        emoji = TIER_EMOJI.get(tier.prize_type, "🎁")
        type_label = {"jackpot": "[gold1]Jackpot[/gold1]",
                      "variable": "[cyan]Variável[/cyan]",
                      "fixed": f"[green]R$ {tier.fixed_value:.2f}[/green]"}.get(tier.prize_type, "—")
        table.add_row(
            f"[{color}]{tier.name}[/{color}]",
            row["percent"],
            f"[bold]{row['odds']}[/bold]",
            row["coin_flips"],
            f"{emoji} {type_label}",
        )

    console.print(table)

    # Overall
    console.print(Panel(
        f"Chance de ganhar qualquer prêmio: [bold cyan]{overall_win_probability(cfg, n_picks) * 100:.4f}%[/bold cyan]"
        f"  ({odds_string(overall)})\n\n"
        f"[dim]Preço da aposta: R$ {cfg.ticket_price:.2f}   |   "
        f"Sorteios: {cfg.draw_days}[/dim]",
        title="📊 Probabilidade Total",
        border_style="magenta",
    ))

    _show_comparison_table()


def _show_comparison_table():
    if not questionary.confirm(
        "Ver tabela comparativa entre todos os jogos?", default=False, style=_qs()
    ).ask():
        return

    table = Table(title="Comparação de Odds – Jackpot", box=box.ROUNDED, border_style="yellow")
    table.add_column("Jogo",          style="bold")
    table.add_column("Odds Jackpot",  justify="right")
    table.add_column("Preço",         justify="right", style="cyan")
    table.add_column("Sorteios/semana", justify="center", style="dim")

    for lt, cfg in LOTTERY_CONFIGS.items():
        from services.probability import calculate_prize_probabilities
        rows = calculate_prize_probabilities(cfg, cfg.min_picks)
        jackpot_row = next((r for r in rows if r["tier"].prize_type == "jackpot"), None)
        odds = jackpot_row["odds"] if jackpot_row else "—"
        table.add_row(
            f"{cfg.emoji} {cfg.display_name}",
            odds,
            f"R$ {cfg.ticket_price:.2f}",
            cfg.draw_days.split("(")[0].strip(),
        )

    console.print(table)


# ─────────────────────────── history ────────────────────────────────────────

def _show_history(store: Store):
    console.print(Rule("[bold yellow]Histórico de Sorteios[/bold yellow]"))
    draws = store.get_draws()
    if not draws:
        console.print("[yellow]Nenhum sorteio salvo ainda.[/yellow]")
        return

    table = Table(box=box.ROUNDED, border_style="dim")
    table.add_column("Concurso", style="yellow")
    table.add_column("Jogo",     style="bold")
    table.add_column("Data",     style="dim")
    table.add_column("Números",  style="cyan")
    table.add_column("Extra",    style="magenta")

    for d in draws[-20:]:    # show last 20
        cfg = LOTTERY_CONFIGS[d.lottery_type]
        nums = "  ".join(str(n).zfill(2) for n in sorted(d.numbers))
        extra = "—"
        if d.extra is not None:
            if d.lottery_type == LotteryType.TIMEMANIA:
                extra = f"⚽ {TIMEMANIA_TEAMS.get(d.extra, d.extra)}"
            elif d.lottery_type == LotteryType.DIA_DE_SORTE:
                extra = f"☀️ {DIA_DE_SORTE_MONTHS.get(d.extra, d.extra)}"
            elif d.lottery_type == LotteryType.MAIS_MILIONARIA:
                extra = f"💎 {d.extra}"
        table.add_row(d.contest_number or "—", f"{cfg.emoji} {cfg.display_name}",
                      d.draw_date or "—", nums, extra)

    console.print(table)


# ─────────────────────────── main menu ──────────────────────────────────────

def run_app():
    store = Store()
    _banner()

    while True:
        ticket_count = len(store.get_tickets())
        console.print()

        action = questionary.select(
            "O que deseja fazer?",
            choices=[
                questionary.Choice(title="🎲  Gerar jogos + exportar Excel",   value="gen"),
                questionary.Choice(title="➕  Adicionar jogo manualmente",      value="add"),
                questionary.Choice(title=f"📋  Ver meus jogos ({ticket_count})", value="list"),
                questionary.Choice(title="🔍  Conferir sorteio",                value="check"),
                questionary.Choice(title="📊  Probabilidades de ganhar",        value="prob"),
                questionary.Choice(title="🕐  Histórico de sorteios",           value="history"),
                questionary.Choice(title="🗑️  Remover jogo",                   value="remove"),
                questionary.Choice(title="🚪  Sair",                            value="exit"),
            ],
            style=_qs(),
        ).ask()

        if action is None or action == "exit":
            console.print("\n[bold yellow]Boa sorte! 🍀[/bold yellow]\n")
            sys.exit(0)

        console.print()

        if action == "gen":
            _generate_games(store)
        elif action == "add":
            _add_ticket(store)
        elif action == "list":
            _list_tickets(store)
        elif action == "check":
            _check_draw(store)
        elif action == "prob":
            _show_probability(store)
        elif action == "history":
            _show_history(store)
        elif action == "remove":
            _remove_ticket(store)
