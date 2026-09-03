import html
from datetime import date
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

try:
    from .data_helpers import load_pairing_counts, load_pairing_history, load_reserve_assignments
    from .score_helpers import compute_standings, load_scores
except ImportError:
    from data_helpers import load_pairing_counts, load_pairing_history, load_reserve_assignments
    from score_helpers import compute_standings, load_scores


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "pairings_history.csv"
PAIRINGS_FILE = DATA_DIR / "pairings.csv"
SCORES_FILE = DATA_DIR / "scores_history.csv"
RESERVE_ASSIGNMENTS_FILE = DATA_DIR / "reserve_assignments.csv"


def _history_dates():
    return sorted(load_pairing_history(HISTORY_FILE), reverse=True)


def _scores_input_id(play_date):
    return f"mirror_scores_{play_date.replace('-', '_')}"


def _history_view():
    history = load_pairing_history(HISTORY_FILE)
    if not history:
        return ui.div("Nog geen speeldagen gevonden.", class_="empty-state")
    today = date.today().isoformat()
    future_dates = sorted(item for item in history if item > today)
    played_dates = sorted((item for item in history if item <= today), reverse=True)
    sections = []
    if future_dates:
        sections.append(ui.h2("Toekomstige speeldag", class_="history-section-title"))
    for play_date in future_dates + played_dates:
        reserve_names = load_reserve_assignments(RESERVE_ASSIGNMENTS_FILE).get(play_date, {})
        tables = []
        for table, players in history[play_date]:
            tables.append(ui.div(
                ui.div(f"Tafel {table}", class_="history-table-title"),
                ui.div(*[
                    ui.div(
                        html.escape(reserve_names.get(player, player)),
                        class_="player-chip reserve" if player.startswith("Reserve ") else "player-chip",
                    )
                    for player in players
                ], class_="player-grid"),
                class_="history-table",
            ))
        sections.append(ui.tags.section(
            ui.div(
                ui.h3(play_date),
                ui.tags.button(
                    "Scores", type="button", class_="scores-button",
                    onclick=f"window.Shiny.setInputValue('score_navigation', '{play_date}', {{priority:'event'}})",
                ),
                class_="history-header",
            ),
            ui.div(*tables, class_="history-tables"), class_="history-day"
        ))
        if played_dates and play_date == played_dates[0]:
            sections.insert(len(sections) - 1, ui.h2("Gespeelde dagen", class_="history-section-title"))
    return ui.div(*sections)


def _scores_view(play_date=None):
    rows = load_scores(str(SCORES_FILE), play_date or None)
    if not rows:
        return ui.div("Nog geen scores gevonden.", class_="empty-state")
    return ui.div(ui.tags.table(
        ui.tags.thead(ui.tags.tr(
            ui.tags.th("Tafel"), ui.tags.th("Spel"), ui.tags.th("Team 1"),
            ui.tags.th("Score"), ui.tags.th("Team 2"), ui.tags.th("Score"),
        )),
        ui.tags.tbody(*[
            ui.tags.tr(
                ui.tags.td(str(row["Table"])), ui.tags.td(str(row["Game"])),
                ui.tags.td(row["Team1Players"].replace("|", " + ")),
                ui.tags.td(str(row["Team1Score"]), class_="numeric"),
                ui.tags.td(row["Team2Players"].replace("|", " + ")),
                ui.tags.td(str(row["Team2Score"]), class_="numeric"),
            ) for row in rows
        ]), class_="data-table"
    ), class_="table-scroll")


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
            h1,h2,h3 { font-family:'Space Grotesk',sans-serif; } .app-shell { max-width:1180px; margin:auto; padding:0 22px 64px; }
            .eyebrow { color:var(--teal); font-weight:700; letter-spacing:.12em; font-size:.75rem; } .intro { margin-bottom:26px; padding-top:38px; }
            .intro h1 { font-size:clamp(2.3rem,5vw,4.3rem); line-height:.98; max-width:700px; margin:10px 0 14px; } .intro p { color:var(--muted); max-width:650px; font-size:1.05rem; }
            .mirror-navigation-group { position:relative; } .mobile-nav-bar { display:none; } .nav-tabs { position:sticky; top:0; z-index:1000; display:flex; justify-content:flex-end; align-items:center; border-bottom:1px solid var(--line); margin-bottom:22px; padding:6px 0 0; background:rgba(244,241,234,.96); box-shadow:0 5px 14px rgba(24,35,43,.08); backdrop-filter:blur(8px); } .nav-tabs::before { content:"Manillen | Publieke mirror"; margin-right:auto; padding:0 15px 12px 0; color:var(--teal); font-family:'Space Grotesk',sans-serif; font-weight:700; white-space:nowrap; } .nav-tabs .nav-link { color:var(--muted); font-weight:700; padding:12px 15px; } .nav-tabs .nav-link.active { color:var(--teal); border-color:var(--teal); background:transparent; }
            .panel { background:rgba(255,253,248,.84); border:1px solid var(--line); padding:24px; box-shadow:0 12px 35px rgba(24,35,43,.05); } .panel h2 { margin-top:0; }
            .history-day { border-top:1px solid var(--line); padding:22px 0; } .history-header { display:flex; justify-content:space-between; align-items:center; gap:12px; } .history-day h3 { margin:0 0 14px; } .history-section-title { margin:28px 0 0; } .scores-button { color:var(--teal); border-color:var(--teal); background:transparent; } .history-tables { display:grid; grid-template-columns:repeat(auto-fit,minmax(245px,1fr)); gap:10px; } .history-table { border-left:3px solid var(--gold); padding:12px; background:#fffaf0; }
            .history-table-title { font-family:'Space Grotesk'; font-weight:700; margin-bottom:12px; } .player-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; } .player-chip { background:#e6f0ec; border:1px solid #c8ddd5; padding:10px 8px; min-height:42px; display:flex; align-items:center; }
            .table-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; } .data-table { width:100%; min-width:520px; border-collapse:collapse; background:var(--panel); } .data-table th,.data-table td { text-align:left; padding:12px 13px; border-bottom:1px solid var(--line); } .data-table th { color:var(--teal); font-family:'Space Grotesk'; white-space:nowrap; } .data-table .numeric { text-align:right; font-weight:700; }
            .filter { max-width:360px; margin-bottom:18px; } .filter label { font-weight:700; } .empty-state { color:var(--muted); padding:18px 0; }
            .mobile-nav-toggle { border:1px solid var(--line); border-radius:4px; background:var(--panel); color:var(--ink); min-width:48px; min-height:44px; padding:8px 12px; box-shadow:0 3px 10px rgba(24,35,43,.08); cursor:pointer; } .hamburger-icon { display:block; width:22px; height:16px; border-top:2px solid currentColor; border-bottom:2px solid currentColor; position:relative; } .hamburger-icon::after { content:""; position:absolute; left:0; right:0; top:5px; border-top:2px solid currentColor; }
            .mobile-nav-brand { color:var(--teal); font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1rem; }
            @media (max-width:600px) { .app-shell { padding:0 14px 50px; } .intro { padding-top:28px; } .panel { padding:17px; } .history-tables { display:block; } .history-table { margin-bottom:10px; } .player-grid { gap:6px; } .mobile-nav-bar { display:flex; position:sticky; top:0; z-index:1001; justify-content:space-between; align-items:center; height:52px; background:rgba(244,241,234,.97); border-bottom:1px solid var(--line); box-shadow:0 5px 14px rgba(24,35,43,.08); } .nav-tabs::before { display:none; } .nav-tabs { display:none; position:relative; top:auto; margin-bottom:22px; padding:0; box-shadow:none; backdrop-filter:none; overflow:visible; } .mirror-navigation-group.is-open .nav-tabs { display:flex; flex-direction:column; flex-wrap:nowrap; position:fixed; top:52px; left:14px; right:14px; z-index:1000; margin:0; padding:6px 0; background:var(--panel); border:1px solid var(--line); box-shadow:0 8px 20px rgba(24,35,43,.16); } .nav-tabs .nav-link { white-space:normal; width:100%; padding:13px 12px; } }
        """),
    ),
    ui.div(
        ui.div(
            ui.div("Manillen | Publieke mirror", class_="mobile-nav-brand"),
            ui.tags.button(
                ui.tags.span(class_="hamburger-icon", aria_hidden="true"),
                id="mobile-nav-toggle", type="button", class_="mobile-nav-toggle",
                aria_label="Open navigatie", aria_expanded="false",
            ),
            class_="mobile-nav-bar",
        ),
        ui.navset_tab(
            ui.nav_panel("Geschiedenis", ui.div(ui.h2("Speeldagen"), ui.output_ui("history"), class_="panel")),
            ui.nav_panel("Scores", ui.div(ui.h2("Scores"), ui.input_select("scores_date", "Speeldag", {"": "Alle speeldagen", **history_choices}), ui.output_ui("scores"), class_="panel")),
            ui.nav_panel("Tussenstand", ui.div(ui.h2("Tussenstand"), ui.input_select("standings_date", "Periode", {"": "Alle speeldagen (cumulatief)", **history_choices}), ui.output_ui("standings"), class_="panel")),
            ui.nav_panel("Parenhistoriek", ui.div(ui.h2("Parenhistoriek"), ui.input_selectize("pairing_player", "Zoek speler", choices={"": "Alle spelers", **{player: player for player in players}}, selected="", options={"placeholder": "Typ een naam...", "allowEmptyOption": True}), ui.output_ui("pairings"), class_="panel")),
            id="tabs",
        ),
        ui.tags.script("""
            (() => {
                const init = () => {
                    const group = document.querySelector('.mirror-navigation-group');
                    const button = document.querySelector('#mobile-nav-toggle');
                    if (!group || !button || group.dataset.ready === 'true') return;
                    group.dataset.ready = 'true';
                    const close = () => {
                        group.classList.remove('is-open');
                        button.setAttribute('aria-expanded', 'false');
                        button.setAttribute('aria-label', 'Open navigatie');
                    };
                    button.addEventListener('click', () => {
                        const isOpen = group.classList.toggle('is-open');
                        button.setAttribute('aria-expanded', String(isOpen));
                        button.setAttribute('aria-label', isOpen ? 'Sluit navigatie' : 'Open navigatie');
                    });
                    group.querySelectorAll('.nav-link').forEach((link) => link.addEventListener('click', close));
                };
                if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
            })();
        """),
        class_="mirror-navigation-group",
    ),
    ui.div(
        ui.div("MANILLEN / PUBLIEKE MIRROR", class_="eyebrow"),
        ui.h1("Manillen before dark: de speeldagen, helder bijgehouden."),
        ui.p("Een actuele, alleen-lezen momentopname van geschiedenis, tussenstand en parenhistoriek."),
        class_="intro",
    ),
    class_="app-shell",
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
    def scores():
        refresh()
        return _scores_view(input.scores_date() or None)

    @reactive.effect
    @reactive.event(input.score_navigation)
    def scores_navigation():
        play_date = input.score_navigation()
        ui.update_select("scores_date", selected=play_date)
        ui.update_navset("tabs", selected="Scores")

    @render.ui
    def pairings():
        refresh()
        return _pairings_view(input.pairing_player() or "")


app = App(app_ui, server)