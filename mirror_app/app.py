import html
from datetime import date
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

try:
    from .data_helpers import (
        load_pairing_counts,
        load_pairing_history,
        load_reserve_assignments,
    )
    from .score_helpers import compute_standings, load_scores
except ImportError:
    from data_helpers import (
        load_pairing_counts,
        load_pairing_history,
        load_reserve_assignments,
    )
    from score_helpers import compute_standings, load_scores


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "pairings_history.csv"
PAIRINGS_FILE = DATA_DIR / "pairings.csv"
SCORES_FILE = DATA_DIR / "scores_history.csv"
RESERVE_ASSIGNMENTS_FILE = DATA_DIR / "reserve_assignments.csv"
STYLE_FILE = BASE_DIR / "manillen.css"
if not STYLE_FILE.exists():
    STYLE_FILE = BASE_DIR.parent / "www" / "manillen.css"
APP_CSS = STYLE_FILE.read_text(encoding="utf-8")


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
        reserve_names = load_reserve_assignments(RESERVE_ASSIGNMENTS_FILE).get(
            play_date, {}
        )
        tables = []
        for table, players in history[play_date]:
            tables.append(
                ui.div(
                    ui.div(f"Tafel {table}", class_="history-table-title"),
                    ui.div(
                        *[
                            ui.div(
                                html.escape(reserve_names.get(player, player)),
                                class_=(
                                    "player-chip reserve"
                                    if player.startswith("Reserve ")
                                    else "player-chip"
                                ),
                            )
                            for player in players
                        ],
                        class_="player-grid",
                    ),
                    class_="history-table",
                )
            )
        sections.append(
            ui.tags.section(
                ui.div(
                    ui.h3(play_date),
                    ui.tags.button(
                        "Scores",
                        type="button",
                        class_="scores-button",
                        onclick=f"window.Shiny.setInputValue('score_navigation', '{play_date}', {{priority:'event'}})",
                    ),
                    class_="history-header",
                ),
                ui.div(*tables, class_="history-tables"),
                class_="history-day",
            )
        )
        if played_dates and play_date == played_dates[0]:
            sections.insert(
                len(sections) - 1,
                ui.h2("Gespeelde dagen", class_="history-section-title"),
            )
    return ui.div(*sections)


def _scores_view(play_date=None, selected_player=""):
    rows = load_scores(str(SCORES_FILE), play_date or None)
    if selected_player:
        rows = [
            row for row in rows
            if selected_player.casefold() in row["Team1Players"].casefold()
            or selected_player.casefold() in row["Team2Players"].casefold()
        ]
    if not rows:
        return ui.div("Nog geen scores gevonden.", class_="empty-state")
    return ui.div(ui.tags.table(
        ui.tags.thead(ui.tags.tr(
            ui.tags.th("Datum"), ui.tags.th("Tafel"), ui.tags.th("Spel"), ui.tags.th("Team 1"),
            ui.tags.th("Score"), ui.tags.th("Team 2"), ui.tags.th("Score"),
        )),
        ui.tags.tbody(*[
            ui.tags.tr(
                ui.tags.td(str(row["Date"])), ui.tags.td(str(row["Table"])), ui.tags.td(str(row["Game"])),
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

    medal_classes = {0: "rank-gold", 1: "rank-silver", 2: "rank-bronze"}
    medal_emojis = {0: "🥇", 1: "🥈", 2: "🥉"}
    active_indices = [i for i, row in enumerate(rows) if row["games_played"] > 0]
    last_active_index = active_indices[-1] if active_indices else None

    table_rows = []
    for index, row in enumerate(rows):
        row_classes = []
        emoji = ""
        if index in medal_classes:
            row_classes.append(medal_classes[index])
            emoji = medal_emojis[index]
        elif index == last_active_index:
            row_classes.append("rank-lantern")
            emoji = "🏮"

        player_display = f"{emoji} {row['player']}" if emoji else row["player"]
        tr_kwargs = {"class_": " ".join(row_classes)} if row_classes else {}

        table_rows.append(
            ui.tags.tr(
                ui.tags.td(str(index + 1)),
                ui.tags.td(player_display),
                ui.tags.td(str(row["wins"])),
                ui.tags.td(str(row["games_played"])),
                ui.tags.td(str(row["points_for"]), class_="numeric"),
                ui.tags.td(str(row["points_against"]), class_="numeric"),
                ui.tags.td(str(row["point_diff"]), class_="numeric"),
                **tr_kwargs,
            )
        )

    return ui.div(
        ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("#"),
                    ui.tags.th("Speler"),
                    ui.tags.th("Gewonnen"),
                    ui.tags.th("Gespeeld"),
                    ui.tags.th("Voor"),
                    ui.tags.th("Tegen"),
                    ui.tags.th("Saldo"),
                )
            ),
            ui.tags.tbody(*table_rows),
            class_="data-table",
        ),
        class_="table-scroll",
    )


def _pairings_view(selected_player=""):
    rows = [row for row in load_pairing_counts(PAIRINGS_FILE) if row[2] > 0]
    if selected_player:
        rows = [
            row
            for row in rows
            if selected_player.casefold() in row[0].casefold()
            or selected_player.casefold() in row[1].casefold()
        ]
    rows.sort(key=lambda row: (-row[2], row[0].casefold(), row[1].casefold()))
    if not rows:
        return ui.div("Geen paringen gevonden.", class_="empty-state")
    return ui.div(
        ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Speler 1"),
                    ui.tags.th("Speler 2"),
                    ui.tags.th("Samen gespeeld"),
                )
            ),
            ui.tags.tbody(
                *[
                    ui.tags.tr(
                        ui.tags.td(a),
                        ui.tags.td(b),
                        ui.tags.td(str(count), class_="numeric"),
                    )
                    for a, b, count in rows
                ]
            ),
            class_="data-table",
        ),
        class_="table-scroll",
    )


players = sorted(
    {player for rows in load_pairing_counts(PAIRINGS_FILE) for player in rows[:2]},
    key=str.casefold,
)
history_choices = {item: item for item in _history_dates()}

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.meta(name="viewport", content="width=device-width, initial-scale=1"),
        ui.tags.title("Manillen | Publieke mirror"),
        ui.tags.style(APP_CSS),
    ),
    ui.div(
        ui.div(
            ui.div("Manillen | Publieke mirror", class_="mobile-nav-brand"),
            ui.tags.button(
                ui.tags.span(class_="hamburger-icon", aria_hidden="true"),
                id="mobile-nav-toggle",
                type="button",
                class_="mobile-nav-toggle",
                aria_label="Open navigatie",
                aria_expanded="false",
            ),
            class_="mobile-nav-bar",
        ),
        ui.navset_tab(
            ui.nav_panel(
                "Tussenstand",
                ui.div(
                    ui.h2("Tussenstand"),
                    ui.input_select(
                        "standings_date",
                        "Periode",
                        {"": "Alle speeldagen (cumulatief)", **history_choices},
                    ),
                    ui.output_ui("standings"),
                    class_="panel",
                ),
            ),
            ui.nav_panel(
                "Speeldagen",
                ui.div(ui.h2("Speeldagen"), ui.output_ui("history"), class_="panel"),
            ),
            ui.nav_panel(
                "Scores",
                ui.div(
                    ui.h2("Scores"),
                    ui.input_select(
                        "scores_date",
                        "Speeldag",
                        {"": "Alle speeldagen", **history_choices},
                    ),
                    ui.input_selectize(
                        "scores_player",
                        "Filter op speler",
                        choices={
                            "": "Alle spelers",
                            **{player: player for player in players},
                        },
                        selected="",
                        options={
                            "placeholder": "Typ een naam...",
                            "allowEmptyOption": True,
                        },
                    ),
                    ui.output_ui("scores"),
                    class_="panel",
                ),
            ),
            ui.nav_panel(
                "Parenhistoriek",
                ui.div(
                    ui.h2("Parenhistoriek"),
                    ui.input_selectize(
                        "pairing_player",
                        "Zoek speler",
                        choices={
                            "": "Alle spelers",
                            **{player: player for player in players},
                        },
                        selected="",
                        options={
                            "placeholder": "Typ een naam...",
                            "allowEmptyOption": True,
                        },
                    ),
                    ui.output_ui("pairings"),
                    class_="panel",
                ),
            ),
            id="tabs",
            selected="Tussenstand",
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
        ui.p(
            "Een actuele, alleen-lezen momentopname van speeldagen, tussenstand en parenhistoriek."
        ),
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
        return _scores_view(input.scores_date() or None, input.scores_player() or "")

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
