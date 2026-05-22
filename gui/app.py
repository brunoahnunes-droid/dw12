"""
GUI – Conferidor de Loterias Caixa
CustomTkinter (dark/light) + ttk.Treeview
Compatível com PyInstaller --onefile --windowed
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

import customtkinter as ctk

# ── ensure project root is importable when frozen by PyInstaller ──────────────
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.lottery_types import (
    LOTTERY_CONFIGS, LotteryType,
    TIMEMANIA_TEAMS, DIA_DE_SORTE_MONTHS,
)
from models.ticket import DrawResult, Ticket
from services.checker import CheckResult, check_ticket
from services.excel_export import export_check_results, export_generated_games
from services.generator import generate_games
from services.probability import calculate_prize_probabilities, overall_win_probability
from storage.store import Store

# ── constants ─────────────────────────────────────────────────────────────────
GOLD       = "#FFD700"
GOLD_DARK  = "#B8860B"
SIDEBAR_W  = 230
WIN_W, WIN_H = 1340, 820

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

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "exports")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ─────────────────────────────── helpers ─────────────────────────────────────

def _lt_choices() -> list[tuple[str, LotteryType]]:
    return [(f"{c.emoji}  {c.display_name}", lt)
            for lt, c in LOTTERY_CONFIGS.items()]


def _treeview_style(mode: str = "dark"):
    style = ttk.Style()
    style.theme_use("clam")
    bg  = "#1e1e2e" if mode == "dark" else "#f5f5f5"
    fg  = "#ffffff" if mode == "dark" else "#111111"
    hbg = "#16162a" if mode == "dark" else "#e0e0e0"
    sbg = "#FFD700"
    sfg = "#000000"
    style.configure("Lot.Treeview",
        background=bg, foreground=fg, fieldbackground=bg,
        rowheight=34, font=("Segoe UI", 11), borderwidth=0,
    )
    style.configure("Lot.Treeview.Heading",
        background=hbg, foreground=GOLD,
        font=("Segoe UI", 11, "bold"), relief="flat", padding=6,
    )
    style.map("Lot.Treeview",
        background=[("selected", sbg)],
        foreground=[("selected", sfg)],
    )


def _scrolled_tree(parent, columns: list[tuple[str, int, str]],
                   height: int = 14) -> ttk.Treeview:
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, style="Lot.Treeview",
                        columns=[c[0] for c in columns],
                        show="headings", height=height,
                        selectmode="browse")
    for col_id, col_w, col_label in columns:
        tree.heading(col_id, text=col_label)
        tree.column(col_id, width=col_w, minwidth=50, anchor="center")

    vsb = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal",  command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    return tree


# ─────────────────────────────── BaseView ────────────────────────────────────

class BaseView(ctk.CTkFrame):
    def __init__(self, parent, app: "LoteriasApp"):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self.store = app.store
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self): ...
    def on_show(self): ...

    def _header(self, emoji: str, title: str, subtitle: str):
        hf = ctk.CTkFrame(self, fg_color="#16162a", corner_radius=0, height=72)
        hf.grid(row=0, column=0, sticky="ew")
        hf.grid_propagate(False)
        ctk.CTkLabel(hf, text=f"{emoji}  {title}",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=GOLD).pack(side="left", padx=24, pady=6)
        ctk.CTkLabel(hf, text=subtitle,
                     font=ctk.CTkFont(size=13), text_color="gray70").pack(
                         side="left", padx=0, pady=20)

    def _lt_selector(self, parent, callback=None) -> ctk.CTkOptionMenu:
        labels  = [lbl for lbl, _ in _lt_choices()]
        mapping = {lbl: lt for lbl, lt in _lt_choices()}

        def _on_change(choice):
            if callback:
                callback(mapping[choice])

        menu = ctk.CTkOptionMenu(parent, values=labels,
                                 command=_on_change,
                                 width=240, height=40,
                                 font=ctk.CTkFont(size=13),
                                 fg_color="#2a2a4a", button_color=GOLD_DARK,
                                 dropdown_fg_color="#1e1e2e")
        menu._mapping = mapping
        return menu

    def _card(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, corner_radius=12,
                            fg_color="#1e1e2e", **kwargs)

    def _btn(self, parent, text: str, color: str = GOLD_DARK,
             command=None, **kwargs) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, fg_color=color,
                             hover_color=GOLD, text_color="black" if color == GOLD else "white",
                             font=ctk.CTkFont(size=13, weight="bold"),
                             height=40, corner_radius=8,
                             command=command, **kwargs)


# ──────────────────────────── NumberGrid widget ───────────────────────────────

class NumberGrid(ctk.CTkScrollableFrame):
    """Clickable number grid for selecting lottery numbers."""

    def __init__(self, parent, lo: int, hi: int, cols: int,
                 min_sel: int, max_sel: int,
                 on_change=None, brand_color: str = GOLD_DARK):
        super().__init__(parent, corner_radius=8, fg_color="#1e1e2e")
        self.lo, self.hi   = lo, hi
        self.min_sel       = min_sel
        self.max_sel       = max_sel
        self.on_change     = on_change
        self.brand_color   = brand_color
        self.selected: set[int] = set()
        self._buttons: dict[int, ctk.CTkButton] = {}
        self._build(cols)

    def _build(self, cols: int):
        for widget in self.winfo_children():
            widget.destroy()
        self._buttons.clear()
        for i, n in enumerate(range(self.lo, self.hi + 1)):
            btn = ctk.CTkButton(
                self, text=f"{n:02d}",
                width=52, height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#2a2a2a",
                hover_color="#3a3a3a",
                text_color="gray70",
                command=lambda num=n: self._toggle(num),
            )
            btn.grid(row=i // cols, column=i % cols, padx=3, pady=3)
            self._buttons[n] = btn

    def _toggle(self, n: int):
        if n in self.selected:
            self.selected.discard(n)
            self._buttons[n].configure(fg_color="#2a2a2a", text_color="gray70")
        elif len(self.selected) < self.max_sel:
            self.selected.add(n)
            self._buttons[n].configure(fg_color=self.brand_color, text_color="white")
        if self.on_change:
            self.on_change(sorted(self.selected))

    def reset(self):
        for n in list(self.selected):
            self._buttons[n].configure(fg_color="#2a2a2a", text_color="gray70")
        self.selected.clear()
        if self.on_change:
            self.on_change([])

    def highlight_draw(self, drawn: list[int]):
        """Color drawn numbers gold (for checker view)."""
        for n, btn in self._buttons.items():
            if n in drawn:
                btn.configure(fg_color=GOLD_DARK, text_color="black")
            else:
                btn.configure(fg_color="#2a2a2a", text_color="gray70")
        self.selected = set(drawn)

    def mark_matches(self, ticket_nums: list[int], drawn: list[int]):
        matched = set(ticket_nums) & set(drawn)
        for n, btn in self._buttons.items():
            if n in matched:
                btn.configure(fg_color="#27AE60", text_color="white")
            elif n in drawn:
                btn.configure(fg_color=GOLD_DARK, text_color="black")
            elif n in ticket_nums:
                btn.configure(fg_color="#444466", text_color="gray80")
            else:
                btn.configure(fg_color="#2a2a2a", text_color="gray30")


# ─────────────────────────── GeneratorView ───────────────────────────────────

class GeneratorView(BaseView):
    def _build(self):
        self._header("🎲", "Gerador de Jogos", "  Gera apostas aleatórias e exporta para Excel")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # ── Left panel: controls ──────────────────────────────────────────────
        left = self._card(body, width=300)
        left.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 16))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Tipo de Jogo",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(20, 4))
        self._lt_menu = self._lt_selector(left, callback=self._on_lt_change)
        self._lt_menu.pack(padx=16, pady=(0, 12))

        self._info_card = ctk.CTkFrame(left, fg_color="#252540", corner_radius=10)
        self._info_card.pack(fill="x", padx=16, pady=(0, 16))
        self._info_lbl = ctk.CTkLabel(self._info_card, text="",
                                      font=ctk.CTkFont(size=12),
                                      justify="left", wraplength=240)
        self._info_lbl.pack(padx=12, pady=10)

        ctk.CTkLabel(left, text="Números por jogo",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16)
        self._picks_var = tk.IntVar(value=6)
        self._picks_slider = ctk.CTkSlider(left, from_=6, to=6,
                                            variable=self._picks_var,
                                            command=self._update_cost,
                                            number_of_steps=1,
                                            button_color=GOLD, progress_color=GOLD_DARK)
        self._picks_slider.pack(fill="x", padx=16, pady=4)
        self._picks_lbl = ctk.CTkLabel(left, text="6 números",
                                        font=ctk.CTkFont(size=12), text_color="gray70")
        self._picks_lbl.pack(padx=16)

        ctk.CTkLabel(left, text="Quantidade de jogos",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(16, 0))
        self._games_var = tk.StringVar(value="10")
        games_entry = ctk.CTkEntry(left, textvariable=self._games_var,
                                    width=100, height=36, justify="center",
                                    font=ctk.CTkFont(size=14, weight="bold"))
        games_entry.pack(pady=4)
        games_entry.bind("<KeyRelease>", lambda e: self._update_cost())

        self._cost_lbl = ctk.CTkLabel(left, text="",
                                       font=ctk.CTkFont(size=13),
                                       text_color=GOLD)
        self._cost_lbl.pack(pady=4)

        self._gen_btn = self._btn(left, "🎲  GERAR JOGOS",
                                   command=self._do_generate)
        self._gen_btn.pack(fill="x", padx=16, pady=(16, 6))
        self._export_btn = self._btn(left, "📥  Exportar Excel", color="#1B6E35",
                                      command=self._do_export)
        self._export_btn.pack(fill="x", padx=16, pady=(0, 20))
        self._export_btn.configure(state="disabled")

        # ── Right panel: results ──────────────────────────────────────────────
        right_top = self._card(body)
        right_top.grid(row=0, column=1, sticky="ew", pady=(0, 12))
        self._summary_lbl = ctk.CTkLabel(right_top, text="Gere jogos para ver o resultado aqui.",
                                          font=ctk.CTkFont(size=13), text_color="gray60")
        self._summary_lbl.pack(padx=16, pady=12)

        right_bot = self._card(body)
        right_bot.grid(row=1, column=1, sticky="nsew")

        cols = [("idx","40","#"), ("id","80","ID"), ("nums","520","Números"),
                ("extra","160","Extra"), ("data","150","Gerado em")]
        self._tree = _scrolled_tree(right_bot, cols, height=16)
        self._tree.tag_configure("odd",  background="#1e1e2e")
        self._tree.tag_configure("even", background="#252535")

        self._generated: List[Ticket] = []
        self._current_lt: LotteryType = LotteryType.MEGA_SENA
        self._on_lt_change(LotteryType.MEGA_SENA)

    def _on_lt_change(self, lt: LotteryType):
        self._current_lt = lt
        cfg = LOTTERY_CONFIGS[lt]
        self._picks_slider.configure(from_=cfg.min_picks, to=cfg.max_picks,
                                      number_of_steps=max(1, cfg.max_picks - cfg.min_picks))
        self._picks_var.set(cfg.min_picks)
        if cfg.fixed_picks or cfg.is_positional:
            self._picks_slider.configure(state="disabled")
        else:
            self._picks_slider.configure(state="normal")

        info = (f"Intervalo: {cfg.number_range[0]}–{cfg.number_range[1]}\n"
                f"Picks: {cfg.min_picks}"
                + (f"–{cfg.max_picks}" if cfg.max_picks != cfg.min_picks else "") +
                f"\nPreço: R$ {cfg.ticket_price:.2f}\n"
                f"Sorteio: {cfg.draw_count} números\n"
                f"{cfg.draw_days}")
        self._info_lbl.configure(text=info)
        self._update_cost()

    def _update_cost(self, *_):
        self._picks_lbl.configure(text=f"{self._picks_var.get()} números")
        try:
            n = int(self._games_var.get())
            if n < 1: raise ValueError
        except ValueError:
            self._cost_lbl.configure(text="")
            return
        price = LOTTERY_CONFIGS[self._current_lt].ticket_price
        self._cost_lbl.configure(text=f"💰 Investimento: R$ {n * price:.2f}")

    def _do_generate(self):
        try:
            n_games = int(self._games_var.get())
            if not 1 <= n_games <= 500: raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Informe um número de jogos entre 1 e 500.")
            return

        cfg = LOTTERY_CONFIGS[self._current_lt]
        n_picks = self._picks_var.get()

        self._generated = generate_games(self._current_lt, n_picks, n_games)
        for t in self._generated:
            self.store.add_ticket(t)

        self._refresh_tree()
        self.app.refresh_nav()

        total = n_games * cfg.ticket_price
        self._summary_lbl.configure(
            text=f"✅  {n_games} jogos gerados e salvos  |  "
                 f"R$ {cfg.ticket_price:.2f}/jogo  |  "
                 f"Total: R$ {total:.2f}",
            text_color=GOLD,
        )
        self._export_btn.configure(state="normal")

    def _refresh_tree(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        cfg = LOTTERY_CONFIGS[self._current_lt]
        for i, t in enumerate(self._generated):
            nums = "  ".join(f"{n:02d}" for n in t.numbers)
            extra = self._fmt_extra(t)
            tag = "odd" if i % 2 else "even"
            self._tree.insert("", "end",
                               values=(i+1, t.id, nums, extra, t.created_at),
                               tags=(tag,))

    def _fmt_extra(self, t: Ticket) -> str:
        lt = t.lottery_type
        if t.extra is None: return "—"
        if lt == LotteryType.TIMEMANIA:
            return f"⚽ {TIMEMANIA_TEAMS.get(t.extra, t.extra)}"
        if lt == LotteryType.DIA_DE_SORTE:
            return f"☀️ {DIA_DE_SORTE_MONTHS.get(t.extra, t.extra)}"
        if lt == LotteryType.MAIS_MILIONARIA:
            return f"💎 {t.extra[0]} e {t.extra[1]}"
        return str(t.extra)

    def _do_export(self):
        if not self._generated:
            return
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        path = export_generated_games(self._generated, EXPORTS_DIR)
        messagebox.showinfo("Excel exportado",
                            f"Arquivo salvo em:\n{path}")

    def on_show(self): ...


# ─────────────────────────── ManualAddView ───────────────────────────────────

class ManualAddView(BaseView):
    def _build(self):
        self._header("➕", "Adicionar Jogo Manual",
                     "  Clique nos números para selecionar")

        self._current_lt = LotteryType.MEGA_SENA
        self._grid: Optional[NumberGrid] = None
        self._selected: List[int] = []

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── left controls ──
        left = self._card(body, width=280)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Tipo de Jogo",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(20, 4))
        self._lt_menu = self._lt_selector(left, callback=self._on_lt_change)
        self._lt_menu.pack(padx=16, pady=(0, 12))

        self._counter_lbl = ctk.CTkLabel(left, text="0 / 6 selecionados",
                                          font=ctk.CTkFont(size=16, weight="bold"),
                                          text_color=GOLD)
        self._counter_lbl.pack(pady=8)

        self._min_max_lbl = ctk.CTkLabel(left, text="Selecione entre 6 e 20 números",
                                          font=ctk.CTkFont(size=12), text_color="gray60",
                                          wraplength=240)
        self._min_max_lbl.pack(pady=4)

        # Extra section (hidden by default)
        self._extra_frame = ctk.CTkFrame(left, fg_color="#252540", corner_radius=10)
        self._extra_frame.pack(fill="x", padx=16, pady=8)
        self._extra_lbl = ctk.CTkLabel(self._extra_frame, text="",
                                        font=ctk.CTkFont(size=12, weight="bold"))
        self._extra_lbl.pack(padx=12, pady=(10, 4))
        self._extra_var = tk.StringVar()
        self._extra_menu = ctk.CTkOptionMenu(self._extra_frame, variable=self._extra_var,
                                              values=["—"], width=220, height=36,
                                              fg_color="#2a2a4a", button_color=GOLD_DARK)
        self._extra_menu.pack(padx=12, pady=(0, 8))
        self._extra2_lbl = ctk.CTkLabel(self._extra_frame, text="",
                                         font=ctk.CTkFont(size=12, weight="bold"))
        self._extra2_var = tk.StringVar()
        self._extra2_menu = ctk.CTkOptionMenu(self._extra_frame, variable=self._extra2_var,
                                               values=["—"], width=220, height=36,
                                               fg_color="#2a2a4a", button_color=GOLD_DARK)

        ctk.CTkLabel(left, text="Rótulo (opcional)",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._label_entry = ctk.CTkEntry(left, placeholder_text="Ex: Jogo da família",
                                          width=220, height=36)
        self._label_entry.pack(padx=16)

        self._add_btn = self._btn(left, "✅  SALVAR JOGO", command=self._do_add)
        self._add_btn.pack(fill="x", padx=16, pady=(16, 4))
        self._add_btn.configure(state="disabled")

        self._clear_btn = self._btn(left, "🔄  Limpar", color="#444",
                                     command=self._do_clear)
        self._clear_btn.pack(fill="x", padx=16, pady=(0, 20))

        self._status_lbl = ctk.CTkLabel(left, text="",
                                         font=ctk.CTkFont(size=12), text_color="green",
                                         wraplength=240)
        self._status_lbl.pack(padx=16, pady=4)

        # ── right: number grid ──
        self._grid_container = self._card(body)
        self._grid_container.grid(row=0, column=1, sticky="nsew")

        self._on_lt_change(LotteryType.MEGA_SENA)

    def _on_lt_change(self, lt: LotteryType):
        self._current_lt = lt
        cfg = LOTTERY_CONFIGS[lt]
        brand = BRAND_HEX.get(lt, GOLD_DARK)

        for w in self._grid_container.winfo_children():
            w.destroy()

        lo, hi = cfg.number_range
        total  = hi - lo + 1
        cols   = min(10, max(5, total // 10))

        self._grid = NumberGrid(
            self._grid_container, lo, hi, cols,
            cfg.min_picks, cfg.max_picks,
            on_change=self._on_selection_change,
            brand_color=brand,
        )
        self._grid.pack(fill="both", expand=True, padx=8, pady=8)

        self._selected = []
        self._update_counter()

        # min/max label
        if cfg.fixed_picks or cfg.is_positional:
            self._min_max_lbl.configure(
                text=f"Selecione exatamente {cfg.min_picks} números")
        else:
            self._min_max_lbl.configure(
                text=f"Selecione entre {cfg.min_picks} e {cfg.max_picks} números")

        # Extra config
        self._setup_extra(lt, cfg)

    def _setup_extra(self, lt: LotteryType, cfg):
        for w in [self._extra2_lbl, self._extra2_menu]:
            w.pack_forget()

        if not cfg.extra_name:
            self._extra_frame.pack_forget()
            return

        self._extra_frame.pack(fill="x", padx=16, pady=8)

        if lt == LotteryType.TIMEMANIA:
            self._extra_lbl.configure(text="⚽  Time do Coração")
            vals = [f"{k} – {v}" for k, v in TIMEMANIA_TEAMS.items()]
            self._extra_menu.configure(values=vals)
            self._extra_var.set(vals[0])
            self._extra2_lbl.pack_forget()
            self._extra2_menu.pack_forget()

        elif lt == LotteryType.DIA_DE_SORTE:
            self._extra_lbl.configure(text="☀️  Mês de Sorte")
            vals = [f"{k:02d} – {v}" for k, v in DIA_DE_SORTE_MONTHS.items()]
            self._extra_menu.configure(values=vals)
            self._extra_var.set(vals[0])

        elif lt == LotteryType.MAIS_MILIONARIA:
            self._extra_lbl.configure(text="💎  Trevo 1 (1–6)")
            self._extra_menu.configure(values=[str(i) for i in range(1, 7)])
            self._extra_var.set("1")
            self._extra2_lbl.configure(text="💎  Trevo 2 (1–6)")
            self._extra2_lbl.pack(padx=12, pady=(4, 2))
            self._extra2_menu.configure(values=[str(i) for i in range(1, 7)])
            self._extra2_var.set("2")
            self._extra2_menu.pack(padx=12, pady=(0, 8))

    def _on_selection_change(self, nums: List[int]):
        self._selected = nums
        self._update_counter()

    def _update_counter(self):
        cfg = LOTTERY_CONFIGS[self._current_lt]
        n = len(self._selected)
        self._counter_lbl.configure(text=f"{n} / {cfg.min_picks} selecionados")

        ok = cfg.min_picks <= n <= cfg.max_picks
        self._add_btn.configure(state="normal" if ok else "disabled")
        self._counter_lbl.configure(text_color=GOLD if ok else "white")

    def _get_extra(self):
        lt = self._current_lt
        cfg = LOTTERY_CONFIGS[lt]
        if not cfg.extra_name:
            return None
        val = self._extra_var.get()
        if lt == LotteryType.TIMEMANIA:
            return int(val.split(" – ")[0])
        if lt == LotteryType.DIA_DE_SORTE:
            return int(val.split(" – ")[0])
        if lt == LotteryType.MAIS_MILIONARIA:
            t1 = int(self._extra_var.get())
            t2 = int(self._extra2_var.get())
            return sorted([t1, t2])
        return None

    def _do_add(self):
        label = self._label_entry.get().strip()
        extra = self._get_extra()
        ticket = Ticket.create(self._current_lt, self._selected,
                               extra=extra, label=label)
        self.store.add_ticket(ticket)
        self.app.refresh_nav()
        cfg = LOTTERY_CONFIGS[self._current_lt]
        self._status_lbl.configure(
            text=f"✅ Jogo {ticket.id} salvo!\n{cfg.display_name}",
            text_color="green")
        self._do_clear()

    def _do_clear(self):
        if self._grid:
            self._grid.reset()
        self._selected = []
        self._update_counter()
        self._label_entry.delete(0, "end")
        self._status_lbl.configure(text="")

    def on_show(self): ...


# ──────────────────────────── TicketsView ────────────────────────────────────

class TicketsView(BaseView):
    def _build(self):
        self._header("📋", "Meus Jogos", "  Todos os jogos cadastrados")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Filter bar
        bar = self._card(body)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(padx=16, pady=10, fill="x")

        ctk.CTkLabel(inner, text="Filtrar:", font=ctk.CTkFont(size=13)).pack(side="left")

        choices = [("Todos os jogos", None)] + list(_lt_choices())
        self._filter_var = tk.StringVar(value="Todos os jogos")
        labels  = [lbl for lbl, _ in choices]
        mapping = {lbl: lt for lbl, lt in choices}

        def _on_filter(choice):
            self._filter_lt = mapping.get(choice)
            self._refresh()

        self._filter_lt: Optional[LotteryType] = None
        fmenu = ctk.CTkOptionMenu(inner, values=labels, command=_on_filter,
                                   variable=self._filter_var,
                                   width=220, height=36,
                                   font=ctk.CTkFont(size=13),
                                   fg_color="#2a2a4a", button_color=GOLD_DARK)
        fmenu.pack(side="left", padx=12)

        self._count_lbl = ctk.CTkLabel(inner, text="",
                                        font=ctk.CTkFont(size=13), text_color=GOLD)
        self._count_lbl.pack(side="left", padx=8)

        self._btn(inner, "🗑️  Remover Selecionado", color="#8B0000",
                   command=self._do_remove).pack(side="right")
        self._btn(inner, "🗑️  Limpar Todos", color="#555",
                   command=self._do_clear_all).pack(side="right", padx=8)

        # Table
        table_card = self._card(body)
        table_card.grid(row=1, column=0, sticky="nsew")

        cols = [("id","90","ID"), ("tipo","180","Jogo"),
                ("nums","480","Números"), ("extra","180","Extra"),
                ("label","140","Rótulo"), ("data","160","Data")]
        self._tree = _scrolled_tree(table_card, cols)
        self._tree.tag_configure("odd",  background="#1e1e2e")
        self._tree.tag_configure("even", background="#252535")

    def on_show(self):
        self._refresh()

    def _refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        tickets = self.store.get_tickets(self._filter_lt)
        self._count_lbl.configure(text=f"{len(tickets)} jogo(s)")
        for i, t in enumerate(tickets):
            cfg  = LOTTERY_CONFIGS[t.lottery_type]
            nums = "  ".join(f"{n:02d}" for n in t.numbers[:10])
            if len(t.numbers) > 10:
                nums += f"  … (+{len(t.numbers)-10})"
            extra = self._fmt_extra(t)
            tag   = "odd" if i % 2 else "even"
            self._tree.insert("", "end",
                               values=(t.id, f"{cfg.emoji} {cfg.display_name}",
                                       nums, extra, t.label, t.created_at),
                               tags=(tag,))

    def _fmt_extra(self, t: Ticket) -> str:
        lt = t.lottery_type
        if t.extra is None: return "—"
        if lt == LotteryType.TIMEMANIA:
            return TIMEMANIA_TEAMS.get(t.extra, str(t.extra))
        if lt == LotteryType.DIA_DE_SORTE:
            return DIA_DE_SORTE_MONTHS.get(t.extra, str(t.extra))
        if lt == LotteryType.MAIS_MILIONARIA:
            return f"Trevos {t.extra}"
        return str(t.extra)

    def _do_remove(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um jogo na tabela.")
            return
        tid = self._tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirmar", f"Remover jogo {tid}?"):
            self.store.remove_ticket(str(tid))
            self._refresh()
            self.app.refresh_nav()

    def _do_clear_all(self):
        lt = self._filter_lt
        label = LOTTERY_CONFIGS[lt].display_name if lt else "TODOS"
        if not messagebox.askyesno("Confirmar",
                                    f"Remover {label} jogos? Esta ação não pode ser desfeita."):
            return
        self.store.clear_tickets(lt)
        self._refresh()
        self.app.refresh_nav()


# ──────────────────────────── CheckerView ────────────────────────────────────

class CheckerView(BaseView):
    def _build(self):
        self._header("🔍", "Conferir Sorteio",
                     "  Insira os números sorteados e veja os resultados")

        self._current_lt = LotteryType.MEGA_SENA
        self._results: List[CheckResult] = []

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── Left: inputs ──────────────────────────────────────────────────────
        left = self._card(body, width=320)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Tipo de Jogo",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(20, 4))
        self._lt_menu = self._lt_selector(left, callback=self._on_lt_change)
        self._lt_menu.pack(padx=16, pady=(0, 12))

        ctk.CTkLabel(left, text="Nº do Concurso",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(4, 2))
        self._contest_entry = ctk.CTkEntry(left, placeholder_text="Ex: 2024-001",
                                            height=36, width=220)
        self._contest_entry.pack(padx=16, pady=(0, 8))

        ctk.CTkLabel(left, text="Data do Sorteio",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(4, 2))
        self._date_entry = ctk.CTkEntry(left, placeholder_text="Ex: 22/05/2026",
                                         height=36, width=220)
        self._date_entry.pack(padx=16, pady=(0, 8))

        ctk.CTkLabel(left, text="Números Sorteados",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(4, 2))
        ctk.CTkLabel(left, text="Separe por espaço ou vírgula",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=16)
        self._draw_entry = ctk.CTkEntry(left, placeholder_text="Ex: 5 12 23 34 45 56",
                                         height=42, width=260,
                                         font=ctk.CTkFont(size=14))
        self._draw_entry.pack(padx=16, pady=(2, 8))

        # Dupla-Sena 2nd draw
        self._draw2_frame = ctk.CTkFrame(left, fg_color="transparent")
        ctk.CTkLabel(self._draw2_frame, text="2º Sorteio (Dupla-Sena)",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(4, 2))
        self._draw2_entry = ctk.CTkEntry(self._draw2_frame,
                                          placeholder_text="Ex: 7 14 21 28 35 42",
                                          height=42, width=260,
                                          font=ctk.CTkFont(size=14))
        self._draw2_entry.pack(padx=16, pady=(2, 8))

        # Extra
        self._extra_frame2 = ctk.CTkFrame(left, fg_color="transparent")
        self._extra_lbl2 = ctk.CTkLabel(self._extra_frame2, text="",
                                         font=ctk.CTkFont(size=13, weight="bold"))
        self._extra_lbl2.pack(anchor="w", padx=16, pady=(4, 2))
        self._extra_var2 = tk.StringVar()
        self._extra_menu2 = ctk.CTkOptionMenu(self._extra_frame2, variable=self._extra_var2,
                                               values=["—"], width=260, height=36,
                                               fg_color="#2a2a4a", button_color=GOLD_DARK)
        self._extra_menu2.pack(padx=16, pady=(0, 8))
        self._extra2_frame2 = ctk.CTkFrame(left, fg_color="transparent")
        self._extra2_lbl2 = ctk.CTkLabel(self._extra2_frame2, text="",
                                          font=ctk.CTkFont(size=13, weight="bold"))
        self._extra2_lbl2.pack(anchor="w", padx=16, pady=(4, 2))
        self._extra2_var2 = tk.StringVar()
        self._extra2_menu2 = ctk.CTkOptionMenu(self._extra2_frame2, variable=self._extra2_var2,
                                                values=["—"], width=260, height=36,
                                                fg_color="#2a2a4a", button_color=GOLD_DARK)
        self._extra2_menu2.pack(padx=16, pady=(0, 8))

        self._check_btn = self._btn(left, "🔍  CONFERIR SORTEIO",
                                     command=self._do_check)
        self._check_btn.pack(fill="x", padx=16, pady=(12, 4))
        self._export_btn2 = self._btn(left, "📥  Exportar Excel", color="#1B6E35",
                                       command=self._do_export)
        self._export_btn2.pack(fill="x", padx=16, pady=(0, 8))
        self._export_btn2.configure(state="disabled")
        self._save_btn = self._btn(left, "💾  Salvar no Histórico", color="#1A478C",
                                    command=self._do_save)
        self._save_btn.pack(fill="x", padx=16, pady=(0, 20))
        self._save_btn.configure(state="disabled")

        self._on_lt_change(LotteryType.MEGA_SENA)

        # ── Right: results ────────────────────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Financial summary card
        self._fin_card = self._card(right)
        self._fin_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._fin_lbl = ctk.CTkLabel(self._fin_card,
                                      text="Faça a conferência para ver o resumo financeiro.",
                                      font=ctk.CTkFont(size=13), text_color="gray60")
        self._fin_lbl.pack(padx=20, pady=14)

        # Results table
        table_card = self._card(right)
        table_card.grid(row=1, column=0, sticky="nsew")

        cols = [("id","80","ID"), ("label","110","Rótulo"),
                ("nums","400","Números (verde = acerto)"),
                ("ac","70","Acertos"), ("extra","140","Extra"),
                ("premio","220","Prêmio")]
        self._tree = _scrolled_tree(table_card, cols, height=14)
        self._tree.tag_configure("winner", background="#1a3a1a", foreground="#00FF7F")
        self._tree.tag_configure("odd",    background="#1e1e2e")
        self._tree.tag_configure("even",   background="#252535")

    def _on_lt_change(self, lt: LotteryType):
        self._current_lt = lt
        cfg = LOTTERY_CONFIGS[lt]

        if cfg.has_second_draw:
            self._draw2_frame.pack(fill="x")
        else:
            self._draw2_frame.pack_forget()

        for frm in [self._extra_frame2, self._extra2_frame2]:
            frm.pack_forget()

        if cfg.extra_name:
            self._extra_frame2.pack(fill="x")
            if lt == LotteryType.TIMEMANIA:
                self._extra_lbl2.configure(text="⚽ Time do Coração sorteado")
                vals = [f"{k} – {v}" for k, v in TIMEMANIA_TEAMS.items()]
                self._extra_menu2.configure(values=vals)
                self._extra_var2.set(vals[0])
            elif lt == LotteryType.DIA_DE_SORTE:
                self._extra_lbl2.configure(text="☀️ Mês de Sorte sorteado")
                vals = [f"{k:02d} – {v}" for k, v in DIA_DE_SORTE_MONTHS.items()]
                self._extra_menu2.configure(values=vals)
                self._extra_var2.set(vals[0])
            elif lt == LotteryType.MAIS_MILIONARIA:
                self._extra_lbl2.configure(text="💎 Trevo sorteado 1")
                self._extra_menu2.configure(values=[str(i) for i in range(1, 7)])
                self._extra_var2.set("1")
                self._extra2_frame2.pack(fill="x")
                self._extra2_lbl2.configure(text="💎 Trevo sorteado 2")
                self._extra2_menu2.configure(values=[str(i) for i in range(1, 7)])
                self._extra2_var2.set("2")

    def _parse_draw(self, raw: str) -> Optional[List[int]]:
        try:
            nums = [int(x) for x in raw.replace(",", " ").split() if x]
            return nums if nums else None
        except ValueError:
            return None

    def _get_extra2(self):
        lt = self._current_lt
        cfg = LOTTERY_CONFIGS[lt]
        if not cfg.extra_name: return None
        val = self._extra_var2.get()
        if lt == LotteryType.TIMEMANIA:
            return int(val.split(" – ")[0])
        if lt == LotteryType.DIA_DE_SORTE:
            return int(val.split(" – ")[0])
        if lt == LotteryType.MAIS_MILIONARIA:
            return sorted([int(self._extra_var2.get()), int(self._extra2_var2.get())])
        return None

    def _do_check(self):
        cfg = LOTTERY_CONFIGS[self._current_lt]
        nums = self._parse_draw(self._draw_entry.get())
        if not nums:
            messagebox.showerror("Erro", "Informe os números sorteados.")
            return
        if len(nums) != cfg.draw_count:
            messagebox.showerror("Erro",
                f"Informe exatamente {cfg.draw_count} números. "
                f"Você digitou {len(nums)}.")
            return

        nums2 = None
        if cfg.has_second_draw:
            nums2 = self._parse_draw(self._draw2_entry.get())
            if not nums2 or len(nums2) != cfg.draw_count:
                messagebox.showerror("Erro",
                    f"Informe os {cfg.draw_count} números do 2º sorteio.")
                return

        tickets = self.store.get_tickets(self._current_lt)
        if not tickets:
            messagebox.showinfo("Aviso",
                f"Nenhum jogo cadastrado para {cfg.display_name}.")
            return

        self._draw = DrawResult(
            lottery_type=self._current_lt,
            numbers=sorted(nums),
            numbers2=sorted(nums2) if nums2 else None,
            extra=self._get_extra2(),
            contest_number=self._contest_entry.get().strip(),
            draw_date=self._date_entry.get().strip(),
        )

        self._results = [check_ticket(t, self._draw) for t in tickets]
        self._refresh_results()
        self._refresh_financial()
        self._export_btn2.configure(state="normal")
        self._save_btn.configure(state="normal")

    def _refresh_results(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        cfg = LOTTERY_CONFIGS[self._current_lt]
        draw_set = set(self._draw.numbers)

        for i, r in enumerate(self._results):
            t     = r.ticket
            won   = r.is_winner
            nums  = []
            for n in t.numbers:
                nums.append(f"[{n:02d}]" if n in draw_set else f"{n:02d}")
            nums_str = "  ".join(nums)

            extra_str = "—"
            if r.extra_matches and t.extra is not None:
                lt = self._current_lt
                if lt == LotteryType.TIMEMANIA:
                    extra_str = f"✅ {TIMEMANIA_TEAMS.get(t.extra, t.extra)}"
                elif lt == LotteryType.DIA_DE_SORTE:
                    extra_str = f"✅ {DIA_DE_SORTE_MONTHS.get(t.extra, t.extra)}"
                elif lt == LotteryType.MAIS_MILIONARIA:
                    extra_str = f"✅ {r.extra_matches} trevo(s)"
            elif t.extra is not None:
                if self._current_lt == LotteryType.MAIS_MILIONARIA:
                    extra_str = f"❌ 0 trevo(s)"
                else:
                    extra_str = "❌"

            prize_str = "—"
            if r.best_prize:
                p = r.best_prize
                prize_str = p.name
                if p.prize_type == "fixed":
                    prize_str += f" (R${p.fixed_value:.2f})"

            ac_str = str(r.matches)
            if cfg.has_second_draw and r.matches2:
                ac_str += f" | {r.matches2}"

            tag = "winner" if won else ("odd" if i % 2 else "even")
            self._tree.insert("", "end",
                               values=(t.id, t.label or "—", nums_str,
                                       ac_str, extra_str, prize_str),
                               tags=(tag,))

    def _refresh_financial(self):
        cfg     = LOTTERY_CONFIGS[self._current_lt]
        total   = len(self._results)
        winners = [r for r in self._results if r.is_winner]
        n_win   = len(winners)
        spent   = total * cfg.ticket_price

        fixed = 0.0
        var   = []
        for r in winners:
            for p in [r.prize_tier, r.prize_tier2]:
                if p is None: continue
                if p.prize_type == "fixed":
                    fixed += p.fixed_value
                elif p.name not in var:
                    var.append(p.name)

        net = fixed - spent
        roi = (fixed / spent * 100) if spent else 0
        net_col = "#00FF7F" if net >= 0 else "#FF4444"

        for w in self._fin_card.winfo_children():
            w.destroy()

        row_frame = ctk.CTkFrame(self._fin_card, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=12)

        def stat(parent, label, value, color="white"):
            f = ctk.CTkFrame(parent, fg_color="#252535", corner_radius=10)
            f.pack(side="left", padx=6, pady=4, ipadx=12, ipady=6)
            ctk.CTkLabel(f, text=label,
                         font=ctk.CTkFont(size=11), text_color="gray60").pack()
            ctk.CTkLabel(f, text=value,
                         font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=color).pack()

        stat(row_frame, "Jogos", str(total))
        stat(row_frame, "Premiados", str(n_win), "#00FF7F" if n_win else "gray60")
        stat(row_frame, "Investido", f"R$ {spent:.2f}", "#FF6666")
        stat(row_frame, "Retorno fixo", f"R$ {fixed:.2f}", "#00FF7F")
        stat(row_frame, "Saldo", f"R$ {net:+.2f}", net_col)
        stat(row_frame, "ROI", f"{roi:.1f}%", net_col)
        if var:
            ctk.CTkLabel(self._fin_card,
                         text=f"⚠  Prêmios variáveis: {' | '.join(var)} — consulte a Caixa",
                         font=ctk.CTkFont(size=11), text_color=GOLD).pack(pady=(0, 8))

    def _do_export(self):
        if not self._results: return
        cfg  = LOTTERY_CONFIGS[self._current_lt]
        path = export_check_results(self._results, self._draw, EXPORTS_DIR, cfg.ticket_price)
        messagebox.showinfo("Excel exportado", f"Arquivo salvo em:\n{path}")

    def _do_save(self):
        if not hasattr(self, "_draw"): return
        self.store.save_draw(self._draw)
        self._save_btn.configure(state="disabled", text="💾  Salvo!")
        messagebox.showinfo("Salvo", "Sorteio salvo no histórico.")

    def on_show(self): ...


# ──────────────────────────── ProbabilityView ─────────────────────────────────

class ProbabilityView(BaseView):
    def _build(self):
        self._header("📊", "Probabilidades de Ganhar",
                     "  Cálculo matemático exato por faixa de prêmio")
        self._current_lt = LotteryType.MEGA_SENA

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Controls
        left = self._card(body, width=280)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Tipo de Jogo",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(20, 4))
        self._lt_menu = self._lt_selector(left, callback=self._on_lt_change)
        self._lt_menu.pack(padx=16, pady=(0, 12))

        ctk.CTkLabel(left, text="Números na aposta",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(4, 2))
        self._picks_var2 = tk.IntVar(value=6)
        self._picks_slider2 = ctk.CTkSlider(left, from_=6, to=20,
                                             variable=self._picks_var2,
                                             number_of_steps=14,
                                             button_color=GOLD,
                                             progress_color=GOLD_DARK)
        self._picks_slider2.pack(fill="x", padx=16, pady=4)
        self._picks_lbl2 = ctk.CTkLabel(left, text="6 números",
                                         font=ctk.CTkFont(size=12), text_color="gray70")
        self._picks_lbl2.pack(padx=16)

        self._btn(left, "📊  CALCULAR", command=self._do_calc).pack(
            fill="x", padx=16, pady=(24, 4))

        self._overall_lbl = ctk.CTkLabel(left, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=GOLD, wraplength=240)
        self._overall_lbl.pack(padx=16, pady=8)

        # Table
        right = self._card(body)
        right.grid(row=0, column=1, sticky="nsew")
        cols = [("faixa","250","Faixa de Prêmio"), ("odds","220","Odds (1 em X)"),
                ("pct","180","Probabilidade %"), ("comp","340","Equivale a..."),
                ("tipo","120","Tipo")]
        self._tree = _scrolled_tree(right, cols, height=16)
        self._tree.tag_configure("jackpot",  foreground=GOLD)
        self._tree.tag_configure("variable", foreground="#00BFFF")
        self._tree.tag_configure("fixed",    foreground="#00FF7F")

        self._on_lt_change(LotteryType.MEGA_SENA)
        self._do_calc()

    def _on_lt_change(self, lt: LotteryType):
        self._current_lt = lt
        cfg = LOTTERY_CONFIGS[lt]
        self._picks_slider2.configure(from_=cfg.min_picks, to=cfg.max_picks,
                                       number_of_steps=max(1, cfg.max_picks - cfg.min_picks))
        self._picks_var2.set(cfg.min_picks)
        if cfg.fixed_picks or cfg.is_positional:
            self._picks_slider2.configure(state="disabled")
        else:
            self._picks_slider2.configure(state="normal")
        self._picks_lbl2.configure(text=f"{cfg.min_picks} números")

    def _do_calc(self, *_):
        n = self._picks_var2.get()
        self._picks_lbl2.configure(text=f"{n} números")
        cfg  = LOTTERY_CONFIGS[self._current_lt]
        rows = calculate_prize_probabilities(cfg, n)
        overall = overall_win_probability(cfg, n)

        for row in self._tree.get_children():
            self._tree.delete(row)

        type_label = {"jackpot": "🏆 Jackpot", "variable": "🥈 Variável", "fixed": "💵 Fixo"}
        for r in rows:
            t = r["tier"]
            self._tree.insert("", "end", tags=(t.prize_type,),
                               values=(t.name, r["odds"], r["percent"],
                                       r["coin_flips"],
                                       type_label.get(t.prize_type, "—")))

        self._overall_lbl.configure(
            text=f"Chance total de ganhar:\n{overall*100:.4f}%\n({1/overall:,.0f} apostas em média)")

    def on_show(self): ...


# ──────────────────────────── HistoryView ────────────────────────────────────

class HistoryView(BaseView):
    def _build(self):
        self._header("🕐", "Histórico de Sorteios", "  Sorteios conferidos e salvos")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        bar = self._card(body)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._btn(bar, "🔄  Atualizar", command=self.on_show).pack(
            side="left", padx=16, pady=10)
        self._count_lbl2 = ctk.CTkLabel(bar, text="",
                                         font=ctk.CTkFont(size=13), text_color=GOLD)
        self._count_lbl2.pack(side="left", padx=12, pady=10)

        table_card = self._card(body)
        table_card.grid(row=1, column=0, sticky="nsew")
        cols = [("concurso","100","Concurso"), ("jogo","180","Jogo"),
                ("data","120","Data"), ("nums","440","Números Sorteados"),
                ("extra","180","Extra")]
        self._tree = _scrolled_tree(table_card, cols, height=18)
        self._tree.tag_configure("odd",  background="#1e1e2e")
        self._tree.tag_configure("even", background="#252535")

    def on_show(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        draws = self.store.get_draws()
        self._count_lbl2.configure(text=f"{len(draws)} sorteio(s) salvo(s)")
        for i, d in enumerate(reversed(draws)):
            cfg  = LOTTERY_CONFIGS[d.lottery_type]
            nums = "  ".join(f"{n:02d}" for n in sorted(d.numbers))
            extra = "—"
            if d.extra is not None:
                lt = d.lottery_type
                if lt == LotteryType.TIMEMANIA:
                    extra = TIMEMANIA_TEAMS.get(d.extra, str(d.extra))
                elif lt == LotteryType.DIA_DE_SORTE:
                    extra = DIA_DE_SORTE_MONTHS.get(d.extra, str(d.extra))
                elif lt == LotteryType.MAIS_MILIONARIA:
                    extra = str(d.extra)
            tag = "odd" if i % 2 else "even"
            self._tree.insert("", "end",
                               values=(d.contest_number or "—",
                                       f"{cfg.emoji} {cfg.display_name}",
                                       d.draw_date or "—", nums, extra),
                               tags=(tag,))


# ─────────────────────────── Main Window ─────────────────────────────────────

class LoteriasApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎰  Conferidor de Loterias Caixa")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(1000, 650)

        self.store = Store()
        _treeview_style("dark")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self._show("gen")

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(self, width=SIDEBAR_W, corner_radius=0,
                                      fg_color="#16162a")
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)

        # Logo
        logo = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo.pack(fill="x", pady=(28, 4))
        ctk.CTkLabel(logo, text="🎰", font=ctk.CTkFont(size=48)).pack()
        ctk.CTkLabel(logo, text="LOTERIAS CAIXA",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=GOLD).pack(pady=(4, 0))
        ctk.CTkLabel(logo, text="Conferidor de Apostas",
                     font=ctk.CTkFont(size=11), text_color="gray50").pack()

        ctk.CTkFrame(self._sidebar, height=1, fg_color="#2a2a4a").pack(
            fill="x", padx=16, pady=16)

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        nav = [
            ("🎲", "Gerar Jogos",       "gen"),
            ("➕", "Adicionar Manual",  "add"),
            ("📋", "Meus Jogos",        "tickets"),
            ("🔍", "Conferir Sorteio",  "check"),
            ("📊", "Probabilidades",    "prob"),
            ("🕐", "Histórico",         "history"),
        ]
        for emoji, label, key in nav:
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {emoji}  {label}",
                anchor="w", height=48,
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                hover_color="#2a2a4a",
                text_color="gray70",
                corner_radius=8,
                command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[key] = btn

        # Bottom controls
        ctk.CTkFrame(self._sidebar, height=1, fg_color="#2a2a4a").pack(
            fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(
            self._sidebar, text="  ☀️  Alternar Tema",
            anchor="w", height=40, fg_color="transparent",
            hover_color="#2a2a4a", text_color="gray50",
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme,
        ).pack(fill="x", padx=10, pady=4, side="bottom")

    # ── Content ───────────────────────────────────────────────────────────────

    def _build_content(self):
        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._views: dict[str, BaseView] = {
            "gen":     GeneratorView(self._content, self),
            "add":     ManualAddView(self._content, self),
            "tickets": TicketsView(self._content, self),
            "check":   CheckerView(self._content, self),
            "prob":    ProbabilityView(self._content, self),
            "history": HistoryView(self._content, self),
        }
        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

    def _show(self, key: str):
        for v in self._views.values():
            v.grid_remove()
        self._views[key].grid()
        self._views[key].on_show()

        for k, btn in self._nav_btns.items():
            active = k == key
            btn.configure(
                fg_color=GOLD if active else "transparent",
                text_color="black" if active else "gray70",
                font=ctk.CTkFont(size=14, weight="bold" if active else "normal"),
            )

    def refresh_nav(self):
        count = len(self.store.get_tickets())
        self._nav_btns["tickets"].configure(
            text=f"  📋  Meus Jogos ({count})")

    def _toggle_theme(self):
        mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(mode)
        _treeview_style(mode)


# ─────────────────────────── entry point ─────────────────────────────────────

def run_gui():
    app = LoteriasApp()
    app.mainloop()
