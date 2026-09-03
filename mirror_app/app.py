import html
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

try:
    from .data_helpers import load_pairing_counts, load_pairing_history
    from .score_helpers import compute_standings
except ImportError:
    from data_helpers import load_pairing_counts, load_pairing_history
    from score_helpers import compute_standings


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "pairings_history.csv"
PAIRINGS_FILE = DATA_DIR / "pairings.csv"
SCORES_FILE = DATA_DIR / "scores_history.csv"


def _history_dates():
    return sorted(load_pairing_history(HISTORY_FILE), reverse=True)


def _history_view():
    history = load_pairing_history(HISTORY_FILE)
    if not history:
        return ui.div("Nog geen speeldagen gevonden.", class_="empty-state")
    sections = []
    for play_date in sorted(history, reverse=True):
        tables = []
        for table, players in history[play_date]:
            tables.append(ui.div(
                ui.div(f"Tafel {table}", class_="history-table-title"),
                ui.div(*[ui.div(html.escape(player), class_="player-chip") for player in players], class_="player-grid"),
                class_="history-table",
            ))
        sections.append(ui.tags.section(
            ui.h3(play_date), ui.div(*tables, class_="history-tables"), class_="history-day"
        ))
    return ui.div(*sections)


def _standings_view(play_date=None):
    rows = compute_standings(str(SCORES_FILE), play_date or None)
    if not rows:
        return ui.div("Nog geen scores gevonden.", class_="empty-state")
    table_rows = [ui.tags.tr(
        ui.tags.td(str(index)), ui.tags.td(row["player"]), ui.tags.td(str(row["wins"])),
        ui.tags.td(str(row["games_played"])), ui.tags.td(str(row["point_diff"]), class_="numeric"),
    ) for index, row in enumerate(rows, start=1)]
    return ui.div(ui.tags.table(
        ui.tags.thead(ui.tags.tr(
            ui.tags.th("#"), ui.tags.th("Speler"), ui.tags.th("Gewonnen"),
            ui.tags.th("Gespeeld"), ui.tags.th("Puntensaldo"),
        )), ui.tags.tbody(*table_rows), class_="data-table"
    ), class_="table-scroll")


def _pairings_view(selected_player=""):
    rows = load_pairing_counts(PAIRINGS_FILE)
    if selected_player:
        rows = [row for row in rows if selected_player.casefold() in row[0].casefold() or selected_player.casefold() in row[1].casefold()]
    rows.sort(key=lambda row: (-row[2], row[0].casefold(), row[1].casefold()))
    if not rows:
        return ui.div("Geen paringen gevonden.", class_="empty-state")
    return ui.div(ui.tags.table(
        ui.tags.thead(ui.tags.tr(ui.tags.th("Speler 1"), ui.tags.th("Speler 2"), ui.tags.th("Samen gespeeld"))),
        ui.tags.tbody(*[ui.tags.tr(ui.tags.td(a), ui.tags.td(b), ui.tags.td(str(count), class_="numeric")) for a, b, count in rows]),
        class_="data-table"
    ), class_="table-scroll")


players = sorted({player for rows in load_pairing_counts(PAIRINGS_FILE) for player in rows[:2]}, key=str.casefold)
history_choices = {item: item for item in _history_dates()}

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.meta(name="viewport", content="width=device-width, initial-scale=1"),
        ui.tags.title("Manillen | Publieke mirror"),
        ui.tags.style("""
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@600;700&display=swap');
            :root { --ink:#18232b; --muted:#64747c; --paper:#f4f1ea; --panel:#fffdf8; --teal:#137b73; --gold:#e7a83e; --line:#d9d7cc; }
            * { box-sizing:border-box; } body { margin:0; background:radial-gradient(circle at 90% 0%, #dbeae2 0, transparent 30%), var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }
            h1,h2,h3 { font-family:'Space Grotesk',sans-serif; } .app-shell { max-width:1180px; margin:auto; padding:38px 22px 64px; }
            .eyebrow { color:var(--teal); font-weight:700; letter-spacing:.12em; font-size:.75rem; } .intro { margin-bottom:26px; }
            .intro h1 { font-size:clamp(2.3rem,5vw,4.3rem); line-height:.98; max-width:700px; margin:10px 0 14px; } .intro p { color:var(--muted); max-width:650px; font-size:1.05rem; }
            .nav-tabs { border-bottom:1px solid var(--line); margin-bottom:22px; } .nav-tabs .nav-link { color:var(--muted); font-weight:700; padding:12px 15px; } .nav-tabs .nav-link.active { color:var(--teal); border-color:var(--teal); background:transparent; }
            .panel { background:rgba(255,253,248,.84); border:1px solid var(--line); padding:24px; box-shadow:0 12px 35px rgba(24,35,43,.05); } .panel h2 { margin-top:0; }
            .history-day { border-top:1px solid var(--line); padding:22px 0; } .history-day h3 { margin:0 0 14px; } .history-tables { display:grid; grid-template-columns:repeat(auto-fit,minmax(245px,1fr)); gap:10px; } .history-table { border-left:3px solid var(--gold); padding:12px; background:#fffaf0; }
            .history-table-title { font-family:'Space Grotesk'; font-weight:700; margin-bottom:12px; } .player-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; } .player-chip { background:#e6f0ec; border:1px solid #c8ddd5; padding:10px 8px; min-height:42px; display:flex; align-items:center; }
            .table-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; } .data-table { width:100%; min-width:520px; border-collapse:collapse; background:var(--panel); } .data-table th,.data-table td { text-align:left; padding:12px 13px; border-bottom:1px solid var(--line); } .data-table th { color:var(--teal); font-family:'Space Grotesk'; white-space:nowrap; } .data-table .numeric { text-align:right; font-weight:700; }
            .filter { max-width:360px; margin-bottom:18px; } .filter label { font-weight:700; } .empty-state { color:var(--muted); padding:18px 0; }
            @media (max-width:600px) { .app-shell { padding:28px 14px 50px; } .panel { padding:17px; } .history-tables { display:block; } .history-table { margin-bottom:10px; } .player-grid { gap:6px; } .nav-tabs { overflow-x:auto; flex-wrap:nowrap; } .nav-tabs .nav-link { white-space:nowrap; } }
        """),
    ),
    ui.div(ui.div("MANILLEN / PUBLIEKE MIRROR", class_="eyebrow"), ui.h1("De speeldagen, helder bijgehouden."), ui.p("Een actuele, alleen-lezen momentopname van geschiedenis, tussenstand en parenhistoriek."), class_="intro"),
    ui.navset_tab(
        ui.nav_panel("Geschiedenis", ui.div(ui.h2("Gespeelde dagen"), ui.output_ui("history"), class_="panel")),
        ui.nav_panel("Tussenstand", ui.div(ui.h2("Tussenstand"), ui.input_select("standings_date", "Periode", {"": "Alle speeldagen (cumulatief)", **history_choices}), ui.output_ui("standings"), class_="panel")),
        ui.nav_panel("Parenhistoriek", ui.div(ui.h2("Parenhistoriek"), ui.input_selectize("pairing_player", "Zoek speler", choices={"": "Alle spelers", **{player: player for player in players}}, selected="", options={"placeholder": "Typ een naam...", "allowEmptyOption": True}), ui.output_ui("pairings"), class_="panel")),
        id="tabs",
    ), class_="app-shell",
)


def server(input: Inputs, output: Outputs, session: Session):
    refresh = reactive.Value(0)

    @render.ui
    def history():
        refresh()
        return _history_view()

    @render.ui
    def standings():
        refresh()
        return _standings_view(input.standings_date() or None)

    @render.ui
    def pairings():
        refresh()
        return _pairings_view(input.pairing_player() or "")


app = App(app_ui, server)