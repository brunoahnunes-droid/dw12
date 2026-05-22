"""Flask web application – Conferidor de Loterias Caixa."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import (Flask, flash, redirect, render_template,
                   request, send_file, session, url_for)

from models.lottery_types import (LOTTERY_CONFIGS, LotteryType,
                                   TIMEMANIA_TEAMS, DIA_DE_SORTE_MONTHS)
from models.ticket import DrawResult, Ticket
from services.checker import CheckResult, check_ticket
from services.excel_export import export_check_results, export_generated_games
from services.generator import generate_games
from services.probability import (calculate_prize_probabilities,
                                   odds_string, overall_win_probability)
from storage.store import Store

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.secret_key = "loterias-caixa-2026"

store = Store()


# ─── helpers ─────────────────────────────────────────────────────────────────

BRAND_HEX = {
    LotteryType.MEGA_SENA:       "#1A7F44",
    LotteryType.QUINA:           "#1A478C",
    LotteryType.LOTOFACIL:       "#8B2FC9",
    LotteryType.LOTOMANIA:       "#E35208",
    LotteryType.TIMEMANIA:       "#1B6E35",
    LotteryType.DUPLA_SENA:      "#B71C1C",
    LotteryType.DIA_DE_SORTE:    "#D4820A",
    LotteryType.SUPER_SETE:      "#00838F",
    LotteryType.MAIS_MILIONARIA: "#6A0DAD",
}


def lt_choices():
    return [(cfg.display_name, f"{cfg.emoji}  {cfg.display_name}")
            for cfg in LOTTERY_CONFIGS.values()]


def resolve_lt(name: str) -> LotteryType:
    for lt, cfg in LOTTERY_CONFIGS.items():
        if cfg.display_name == name:
            return lt
    return LotteryType.MEGA_SENA


def cfg_context(lt: LotteryType) -> dict:
    cfg = LOTTERY_CONFIGS[lt]
    return {
        "name": cfg.display_name,
        "emoji": cfg.emoji,
        "description": cfg.description,
        "lo": cfg.number_range[0],
        "hi": cfg.number_range[1],
        "min": cfg.min_picks,
        "max": cfg.max_picks,
        "draw_count": cfg.draw_count,
        "price": cfg.ticket_price,
        "days": cfg.draw_days,
        "fixed": cfg.fixed_picks or cfg.is_positional,
        "positional": cfg.is_positional,
        "extra_name": cfg.extra_name,
        "has_second_draw": cfg.has_second_draw,
        "color": BRAND_HEX.get(lt, "#f5a623"),
        "prizes": [{"name": t.name, "type": t.prize_type,
                    "value": t.fixed_value} for t in cfg.prize_tiers],
    }


def ticket_extra_display(t: Ticket) -> str:
    lt = t.lottery_type
    if t.extra is None:
        return "—"
    if lt == LotteryType.TIMEMANIA:
        return f"⚽ {TIMEMANIA_TEAMS.get(t.extra, t.extra)}"
    if lt == LotteryType.DIA_DE_SORTE:
        return f"☀️ {DIA_DE_SORTE_MONTHS.get(t.extra, t.extra)}"
    if lt == LotteryType.MAIS_MILIONARIA:
        if isinstance(t.extra, list):
            return f"💎 {t.extra[0]} e {t.extra[1]}"
    return str(t.extra)


def draw_extra_display(draw: DrawResult) -> str:
    lt = draw.lottery_type
    if draw.extra is None:
        return ""
    if lt == LotteryType.TIMEMANIA:
        return f"⚽ {TIMEMANIA_TEAMS.get(draw.extra, draw.extra)}"
    if lt == LotteryType.DIA_DE_SORTE:
        return f"☀️ {DIA_DE_SORTE_MONTHS.get(draw.extra, draw.extra)}"
    if lt == LotteryType.MAIS_MILIONARIA:
        ext = draw.extra
        if isinstance(ext, list):
            return f"💎 {ext[0]} e {ext[1]}"
    return str(draw.extra)


def common_ctx():
    return {
        "lt_choices": lt_choices(),
        "ticket_count": len(store.get_tickets()),
    }


# ─── routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    tickets = store.get_tickets()
    draws   = store.get_draws()

    by_type = []
    for lt, cfg in LOTTERY_CONFIGS.items():
        ts = [t for t in tickets if t.lottery_type == lt]
        if ts:
            by_type.append((cfg.display_name, len(ts), cfg.emoji, cfg.ticket_price))

    last_draw = None
    if draws:
        d   = draws[-1]
        cfg = LOTTERY_CONFIGS[d.lottery_type]
        last_draw = {
            "name": cfg.display_name, "emoji": cfg.emoji,
            "contest": d.contest_number, "date": d.draw_date,
            "numbers": sorted(d.numbers),
        }

    excel_count = len([f for f in os.listdir(EXPORTS_DIR)
                       if f.endswith(".xlsx")]) if os.path.exists(EXPORTS_DIR) else 0

    return render_template("index.html", active="index",
                           total_tickets=len(tickets),
                           total_draws=len(draws),
                           excel_count=excel_count,
                           by_type=by_type,
                           last_draw=last_draw,
                           **common_ctx())


@app.route("/gerar", methods=["GET", "POST"])
def gerar():
    selected_lt_name = request.form.get("lottery_type") or \
                       request.args.get("lt") or "Mega-Sena"
    lt  = resolve_lt(selected_lt_name)
    cfg = LOTTERY_CONFIGS[lt]

    n_picks = int(request.form.get("n_picks") or cfg.min_picks)
    n_games = int(request.form.get("n_games") or 10)
    action  = request.form.get("action")

    generated = None

    if action == "generate":
        n_picks = max(cfg.min_picks, min(cfg.max_picks, n_picks))
        n_games = max(1, min(500, n_games))
        tickets = generate_games(lt, n_picks, n_games)
        for t in tickets:
            store.add_ticket(t)
        # Store IDs for export
        session["last_generated"] = [t.id for t in tickets]
        generated = []
        for t in tickets:
            generated.append({
                "id": t.id, "numbers": t.numbers,
                "extra_display": ticket_extra_display(t),
                "created_at": t.created_at,
            })
        flash(f"{n_games} jogos gerados e salvos com sucesso!", "success")

    elif action == "export":
        ids = session.get("last_generated", [])
        all_tickets = store.get_tickets()
        tickets = [t for t in all_tickets if t.id in ids]
        if tickets:
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            path = export_generated_games(tickets, EXPORTS_DIR)
            flash(f"Excel exportado: {os.path.basename(path)}", "success")
        return redirect(url_for("gerar", lt=selected_lt_name))

    return render_template("gerar.html", active="gerar",
                           selected_lt=selected_lt_name,
                           cfg=cfg_context(lt),
                           n_picks=n_picks, n_games=n_games,
                           generated=generated,
                           **common_ctx())


@app.route("/adicionar", methods=["GET", "POST"])
def adicionar():
    selected_lt_name = request.form.get("lottery_type") or \
                       request.args.get("lt") or "Mega-Sena"
    lt  = resolve_lt(selected_lt_name)
    cfg = LOTTERY_CONFIGS[lt]

    if request.form.get("action") == "add":
        raw = request.form.get("numbers", "")
        try:
            nums = [int(x) for x in raw.split(",") if x.strip()]
        except ValueError:
            flash("Números inválidos.", "error")
            return redirect(url_for("adicionar", lt=selected_lt_name))

        lo, hi = cfg.number_range
        if not all(lo <= n <= hi for n in nums):
            flash(f"Todos os números devem estar entre {lo} e {hi}.", "error")
            return redirect(url_for("adicionar", lt=selected_lt_name))
        if not (cfg.min_picks <= len(nums) <= cfg.max_picks):
            flash(f"Selecione entre {cfg.min_picks} e {cfg.max_picks} números.", "error")
            return redirect(url_for("adicionar", lt=selected_lt_name))

        extra = _parse_extra(lt, request.form)
        label = request.form.get("label", "").strip()
        ticket = Ticket.create(lt, nums, extra=extra, label=label)
        store.add_ticket(ticket)
        flash(f"Jogo {ticket.id} salvo com sucesso!", "success")
        return redirect(url_for("adicionar", lt=selected_lt_name))

    return render_template("adicionar.html", active="adicionar",
                           selected_lt=selected_lt_name,
                           cfg=cfg_context(lt),
                           teams=TIMEMANIA_TEAMS,
                           months=DIA_DE_SORTE_MONTHS,
                           **common_ctx())


def _parse_extra(lt: LotteryType, form):
    if lt == LotteryType.TIMEMANIA:
        return int(form.get("extra", 1))
    if lt == LotteryType.DIA_DE_SORTE:
        return int(form.get("extra", 1))
    if lt == LotteryType.MAIS_MILIONARIA:
        t1 = int(form.get("trevo1", 1))
        t2 = int(form.get("trevo2", 2))
        return sorted([t1, t2])
    return None


@app.route("/jogos")
def jogos():
    filter_lt_name = request.args.get("lt", "")
    filter_lt = resolve_lt(filter_lt_name) if filter_lt_name else None
    tickets = store.get_tickets(filter_lt)
    rows = []
    for t in tickets:
        cfg = LOTTERY_CONFIGS[t.lottery_type]
        rows.append({
            "id": t.id, "numbers": t.numbers,
            "lt_name": cfg.display_name, "emoji": cfg.emoji,
            "extra_display": ticket_extra_display(t),
            "label": t.label, "created_at": t.created_at,
        })
    return render_template("jogos.html", active="jogos",
                           tickets=rows, filter_lt=filter_lt_name,
                           **common_ctx())


@app.route("/jogos/remover", methods=["POST"])
def remover_jogo():
    tid = request.form.get("ticket_id", "")
    store.remove_ticket(tid)
    flash(f"Jogo {tid} removido.", "success")
    return redirect(url_for("jogos"))


@app.route("/jogos/limpar", methods=["POST"])
def limpar_jogos():
    lt_name = request.form.get("lt", "")
    lt = resolve_lt(lt_name) if lt_name else None
    removed = store.clear_tickets(lt)
    flash(f"{removed} jogo(s) removido(s).", "success")
    return redirect(url_for("jogos"))


@app.route("/conferir", methods=["GET", "POST"])
def conferir():
    selected_lt_name = request.form.get("lottery_type") or \
                       request.args.get("lt") or "Mega-Sena"
    lt  = resolve_lt(selected_lt_name)
    cfg = LOTTERY_CONFIGS[lt]

    results     = None
    draw        = None
    fin         = None
    extra_disp  = ""
    form_vals   = {"contest": "", "draw_date": "", "numbers": "", "numbers2": "", "extra": ""}
    action      = request.form.get("action")

    if action in ("check", "export", "save_draw"):
        raw     = request.form.get("numbers", "")
        raw2    = request.form.get("numbers2", "")
        contest = request.form.get("contest", "")
        date    = request.form.get("draw_date", "")
        form_vals = {"contest": contest, "draw_date": date,
                     "numbers": raw, "numbers2": raw2}

        try:
            nums = [int(x) for x in raw.replace(",", " ").split() if x]
        except ValueError:
            nums = []

        if action == "check" and len(nums) != cfg.draw_count:
            flash(f"Informe exatamente {cfg.draw_count} números.", "error")
            return redirect(url_for("conferir", lt=selected_lt_name))

        nums2 = None
        if cfg.has_second_draw and raw2:
            try:
                nums2 = [int(x) for x in raw2.replace(",", " ").split() if x]
            except ValueError:
                nums2 = None

        extra = _parse_extra(lt, request.form) if cfg.extra_name else None

        draw = DrawResult(
            lottery_type=lt, numbers=sorted(nums),
            numbers2=sorted(nums2) if nums2 else None,
            extra=extra, contest_number=contest, draw_date=date,
        )

        if action == "export":
            tickets = store.get_tickets(lt)
            res = [check_ticket(t, draw) for t in tickets]
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            path = export_check_results(res, draw, EXPORTS_DIR, cfg.ticket_price)
            flash(f"Excel exportado: {os.path.basename(path)}", "success")

        elif action == "save_draw":
            store.save_draw(draw)
            flash("Sorteio salvo no histórico.", "success")

        elif action == "check":
            tickets = store.get_tickets(lt)
            if not tickets:
                flash(f"Nenhum jogo cadastrado para {cfg.display_name}.", "warn")
            else:
                raw_results = [check_ticket(t, draw) for t in tickets]
                draw_set    = set(nums)
                results     = []
                for r in raw_results:
                    prize = r.best_prize
                    extra_won = r.extra_matches > 0
                    extra_lbl = ""
                    if r.ticket.extra is not None:
                        extra_lbl = ticket_extra_display(r.ticket)

                    results.append({
                        "id": r.ticket.id,
                        "label": r.ticket.label,
                        "numbers": r.ticket.numbers,
                        "matched_set": draw_set & set(r.ticket.numbers),
                        "matches": r.matches,
                        "matches2": r.matches2,
                        "extra_won": extra_won,
                        "extra_label": extra_lbl,
                        "is_winner": r.is_winner,
                        "prize": prize.name if prize else None,
                        "prize_type": prize.prize_type if prize else None,
                        "prize_value": prize.fixed_value if prize and prize.prize_type == "fixed" else None,
                    })

                winners   = [r for r in raw_results if r.is_winner]
                spent     = len(raw_results) * cfg.ticket_price
                fixed_ret = sum(
                    p.fixed_value
                    for r in winners
                    for p in [r.prize_tier, r.prize_tier2] if p and p.prize_type == "fixed"
                )
                var_prizes = list({
                    p.name for r in winners
                    for p in [r.prize_tier, r.prize_tier2]
                    if p and p.prize_type in ("variable", "jackpot")
                })
                net = fixed_ret - spent
                roi = (fixed_ret / spent * 100) if spent else 0
                fin = {"total": len(raw_results), "winners": len(winners),
                       "spent": spent, "ret": fixed_ret, "net": net, "roi": roi,
                       "var_prizes": var_prizes}
                extra_disp = draw_extra_display(draw)

    return render_template("conferir.html", active="conferir",
                           selected_lt=selected_lt_name,
                           cfg=cfg_context(lt),
                           teams=TIMEMANIA_TEAMS,
                           months=DIA_DE_SORTE_MONTHS,
                           results=results, draw=draw,
                           fin=fin, extra_display=extra_disp,
                           form=form_vals,
                           **common_ctx())


@app.route("/probabilidades")
def probabilidades():
    selected_lt_name = request.args.get("lt") or "Mega-Sena"
    lt  = resolve_lt(selected_lt_name)
    cfg = LOTTERY_CONFIGS[lt]

    n_picks = int(request.args.get("picks") or cfg.min_picks)
    n_picks = max(cfg.min_picks, min(cfg.max_picks, n_picks))

    prob_rows = calculate_prize_probabilities(cfg, n_picks)
    overall   = overall_win_probability(cfg, n_picks)

    rows = [{"name": r["tier"].name, "type": r["tier"].prize_type,
             "odds": r["odds"], "pct": r["percent"], "coin": r["coin_flips"]}
            for r in prob_rows]

    # Comparison table (jackpot odds for each game at minimum picks)
    comparison = []
    for comp_lt, comp_cfg in LOTTERY_CONFIGS.items():
        comp_rows = calculate_prize_probabilities(comp_cfg, comp_cfg.min_picks)
        jp = next((r for r in comp_rows if r["tier"].prize_type == "jackpot"), None)
        comparison.append({
            "lt": comp_cfg.display_name,
            "emoji": comp_cfg.emoji,
            "name": comp_cfg.display_name,
            "odds": jp["odds"] if jp else "—",
            "price": comp_cfg.ticket_price,
        })

    return render_template("probabilidades.html", active="probabilidades",
                           selected_lt=selected_lt_name,
                           cfg=cfg_context(lt),
                           n_picks=n_picks, rows=rows,
                           overall_pct=f"{overall*100:.4f}%",
                           overall_odds=odds_string(overall),
                           comparison=comparison,
                           **common_ctx())


@app.route("/historico")
def historico():
    draws = store.get_draws()
    rows  = []
    for d in reversed(draws):
        cfg = LOTTERY_CONFIGS[d.lottery_type]
        rows.append({
            "contest": d.contest_number,
            "lt_name": cfg.display_name,
            "emoji": cfg.emoji,
            "date": d.draw_date,
            "numbers_sorted": sorted(d.numbers),
            "numbers2_sorted": sorted(d.numbers2) if d.numbers2 else None,
            "extra_display": draw_extra_display(d),
        })
    return render_template("historico.html", active="historico",
                           draws=rows, **common_ctx())


# ─── run ─────────────────────────────────────────────────────────────────────

def run_web(host="0.0.0.0", port=5000, debug=False, open_browser=True):
    if open_browser:
        import threading, webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_web(debug=True)
