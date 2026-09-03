import html
import json
import asyncio
from datetime import date
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from manillen_functions import (
    create_player_pool,
    delete_pairings_by_date,
    fill_scorebladen_from_history,
    load_all_players,
    load_pair_counts,
    make_groups_greedy,
    update_pairs_in_csv,
)
from score_functions import compute_standings, get_matchups_for_table, load_scores, save_scores
from mirror_app.data_helpers import load_pairing_counts, load_pairing_history
from reserve_assignments import (
    DEFAULT_ASSIGNMENTS_FILE,
    get_reserve_assignments,
    required_reserve_count,
    save_reserve_assignments,
)
from github_publish import GitHubPublishError, trigger_mirror_workflow


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PAIRINGS = DATA_DIR / "pairings.csv"
ALL_PLAYERS_FILE = DATA_DIR / "AllPlayers.csv"
HISTORY_FILE = DATA_DIR / "pairings_history.csv"
SCOREBLAD_TEMPLATE = DATA_DIR / "Scorebladen.xlsx"
SCOREBLAD_OUTPUT_DIR = DATA_DIR / "Scorebladen"
SCORES_FILE = DATA_DIR / "scores_history.csv"
RESERVE_ASSIGNMENTS_FILE = DEFAULT_ASSIGNMENTS_FILE


def _history_dates():
    return sorted(load_pairing_history(HISTORY_FILE), reverse=True)


def _read_history():
    return {
        play_date: [(str(table), players) for table, players in tables]
        for play_date, tables in load_pairing_history(HISTORY_FILE).items()
    }


def _pairings_table(selected_player=None):
    rows = [row for row in load_pairing_counts(CSV_PAIRINGS) if row[2] > 0]

    if not rows:
        return ui.div("Nog geen paringen gevonden.", class_="empty-state")

    if selected_player:
        rows = [
            row for row in rows
            if selected_player in (row[0], row[1])
        ]

    if not rows:
        return ui.div(f"Geen paringen gevonden voor {selected_player}.", class_="empty-state")

    rows.sort(key=lambda row: (-row[2], row[0].casefold(), row[1].casefold()))
    table_rows = [
        ui.tags.tr(
            ui.tags.td(html.escape(player1)),
            ui.tags.td(html.escape(player2)),
            ui.tags.td(str(count), class_="pair-count"),
        )
        for player1, player2, count in rows
    ]
    return ui.tags.table(
        ui.tags.thead(
            ui.tags.tr(ui.tags.th("Speler 1"), ui.tags.th("Speler 2"), ui.tags.th("Aantal"))
        ),
        ui.tags.tbody(*table_rows),
        class_="pairings-table",
    )


def _score_input_id(table, game, team):
    return f"score_t{table}_g{game}_{team}"


def _scoreblad_file_for_date(play_date):
    if not play_date:
        return None
    path = SCOREBLAD_OUTPUT_DIR / f"scorebladen{play_date.replace('-', '')}.xlsx"
    return path if path.exists() else None


def _score_entry_tables(play_date):
    history = _read_history().get(play_date, [])
    existing = {
        (row["Table"], row["Game"]): row
        for row in load_scores(str(SCORES_FILE), play_date)
    }
    if not history:
        return ui.div("Geen tafels gevonden voor deze speeldag.", class_="empty-state")

    sections = []
    for table_text, table_players in history:
        table = int(table_text)
        games = []
        for game, (team1, team2) in enumerate(get_matchups_for_table(table_players), start=1):
            row = existing.get((table, game), {})
            games.append(
                ui.div(
                    ui.div(f"Spel {game}", class_="score-game-title"),
                    ui.div(" + ".join(team1), class_="score-team"),
                    ui.input_numeric(_score_input_id(table, game, "team1"), "Team 1", value=row.get("Team1Score")),
                    ui.div("vs", class_="score-vs"),
                    ui.input_numeric(_score_input_id(table, game, "team2"), "Team 2", value=row.get("Team2Score")),
                    ui.div(" + ".join(team2), class_="score-team"),
                    class_="score-game",
                )
            )
        sections.append(ui.div(ui.h3(f"Tafel {table}"), ui.div(*games), class_="score-table-card"))
    return ui.div(*sections, class_="score-tables")


def _standings_table(play_date=None):
    rows = compute_standings(str(SCORES_FILE), play_date)
    if not rows:
        return ui.div("Nog geen scores ingevoerd.", class_="empty-state")
    return ui.tags.table(
        ui.tags.thead(ui.tags.tr(
            ui.tags.th("#"), ui.tags.th("Speler"), ui.tags.th("Gewonnen"),
            ui.tags.th("Gespeeld"), ui.tags.th("Voor"), ui.tags.th("Tegen"), ui.tags.th("Saldo")
        )),
        ui.tags.tbody(*[
            ui.tags.tr(
                ui.tags.td(str(index)), ui.tags.td(row["player"]), ui.tags.td(str(row["wins"])),
                ui.tags.td(str(row["games_played"])), ui.tags.td(str(row["points_for"])),
                ui.tags.td(str(row["points_against"])), ui.tags.td(str(row["point_diff"]), class_="pair-count")
            ) for index, row in enumerate(rows, start=1)
        ]),
        class_="pairings-table standings-table",
    )


def _player_name(name, reserve=False):
    safe_name = html.escape(str(name))
    reserve_class = " reserve" if reserve or str(name).startswith("Reserve ") else ""
    return ui.HTML(f'<div class="player-chip{reserve_class}">{safe_name}</div>')


def _delete_input_id(play_date):
    return f"delete_{play_date.replace('-', '_')}"


def _scores_input_id(play_date):
    return f"scores_{play_date.replace('-', '_')}"


def player_selector(player_names, selected=None):
        """Render the client-side typeahead selector for the new-day workflow."""
        selected = selected if selected is not None else []
        player_data = json.dumps(list(player_names), ensure_ascii=False)
        selected_data = json.dumps(list(selected), ensure_ascii=False)
        script = f"""
        (() => {{
            const allPlayers = {player_data};
            const initialSelected = {selected_data};
            const init = () => {{
                const root = document.getElementById('player-selector');
                if (!root || root.dataset.ready === 'true') return;
                root.dataset.ready = 'true';
                const search = root.querySelector('#player-search');
                const suggestions = root.querySelector('#player-suggestions');
                const chips = root.querySelector('#selected-player-chips');
                const count = root.querySelector('#selected-player-count');
                const selected = new Set(initialSelected);
                const publish = () => window.Shiny.setInputValue('selected_players', [...selected], {{priority:'event'}});
                const showSuggestions = () => {{ suggestions.hidden = false; }};
                const hideSuggestions = () => {{ suggestions.hidden = true; }};
                const add = (name) => {{ selected.add(name); search.value = ''; render(); publish(); search.focus(); showSuggestions(); }};
                const render = () => {{
                    const query = search.value.trim().toLocaleLowerCase();
                    const matches = allPlayers.filter((name) => !selected.has(name) && name.toLocaleLowerCase().includes(query));
                    suggestions.innerHTML = '';
                    if (matches.length === 0) {{
                        suggestions.innerHTML = `<div class="suggestion-empty">${{query ? 'Geen speler gevonden' : 'Alle spelers zijn toegevoegd'}}</div>`;
                    }} else {{
                        matches.forEach((name) => {{
                            const option = document.createElement('button'); option.type = 'button'; option.className = 'player-suggestion'; option.textContent = name;
                            option.addEventListener('click', () => add(name)); suggestions.appendChild(option);
                        }});
                    }}
                    chips.innerHTML = '';
                    [...selected].forEach((name) => {{
                        const chip = document.createElement('span'); chip.className = 'selection-chip';
                        const label = document.createElement('span'); label.textContent = name;
                        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `Verwijder ${{name}}`);
                        remove.addEventListener('click', () => {{ selected.delete(name); render(); publish(); search.focus(); showSuggestions(); }});
                        chip.append(label, remove); chips.appendChild(chip);
                    }});
                    const amount = selected.size; const remainder = amount % 4;
                    count.textContent = `${{amount}} speler${{amount === 1 ? '' : 's'}} geselecteerd` + (remainder ? ` · ${{4 - remainder}} reserve nodig` : ' · deelbaar door 4');
                }};
                search.addEventListener('input', () => {{ showSuggestions(); render(); }});
                search.addEventListener('focus', () => {{ showSuggestions(); render(); }});
                search.addEventListener('blur', () => window.setTimeout(hideSuggestions, 150));
                suggestions.addEventListener('mousedown', (event) => event.preventDefault());
                search.addEventListener('keydown', (event) => {{
                    if (event.key !== 'Enter') return; event.preventDefault();
                    const query = search.value.trim().toLocaleLowerCase();
                    const matches = allPlayers.filter((name) => !selected.has(name) && name.toLocaleLowerCase().includes(query));
                    const exact = matches.find((name) => name.toLocaleLowerCase() === query);
                    if (exact || matches.length === 1) add(exact || matches[0]);
                }});
                root.querySelector('#clear-players').addEventListener('click', () => {{ selected.clear(); render(); publish(); search.focus(); showSuggestions(); }});
                render(); publish(); hideSuggestions();
            }};
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
        }})();
        """
        return ui.div(
                ui.tags.label("Spelers", for_="player-search"),
                ui.tags.input(id="player-search", type="text", placeholder="Speler toevoegen…", autocomplete="off"),
                ui.div(id="player-suggestions", class_="player-suggestions", role="listbox", hidden=True),
                ui.div(id="selected-player-chips", class_="selected-player-chips"),
                ui.div(
                        ui.span(id="selected-player-count"),
                        ui.tags.button("Alles wissen", id="clear-players", type="button", class_="clear-players"),
                        class_="selector-footer",
                ),
                ui.tags.script(script), id="player-selector", class_="player-selector"
        )


def _table_cards(config, score=None):
    cards = []
    for number, table in enumerate(config, start=1):
        cards.append(
            ui.div(
                ui.div(f"Tafel {number}", class_="table-title"),
                ui.div(*[_player_name(player) for player in table], class_="player-grid"),
                class_="table-card",
            )
        )
    heading = ui.div(f"Score {score}" if score is not None else "Indeling", class_="score-label")
    return ui.div(heading, ui.div(*cards, class_="tables-grid"), class_="configuration")


def _history_cards():
    history = _read_history()
    if not history:
        return ui.div("Nog geen speeldagen gevonden.", class_="empty-state")

    today = date.today().isoformat()
    future_dates = sorted(item for item in history if item > today)
    played_dates = sorted((item for item in history if item <= today), reverse=True)
    sections = []
    if future_dates:
        sections.append(ui.h2("Toekomstige speeldag", class_="history-section-title"))

    for play_date in future_dates + played_dates:
        reserve_names = get_reserve_assignments(play_date, RESERVE_ASSIGNMENTS_FILE)
        tables = [
            ui.div(
                ui.div(f"Tafel {table}", class_="history-table-title"),
                ui.div(
                    *[_player_name(
                        reserve_names.get(player, player),
                        reserve=player.startswith("Reserve "),
                    ) for player in players],
                    class_="history-players",
                ),
                class_="history-table",
            )
            for table, players in history[play_date]
        ]
        sections.append(
            ui.div(
                ui.div(
                    ui.h3(play_date),
                    ui.tags.button(
                        "Scores", type="button", class_="scores-button",
                        onclick=f"window.Shiny.setInputValue('score_navigation', '{play_date}', {{priority:'event'}})",
                    ),
                    ui.input_action_button(
                        _delete_input_id(play_date), "Verwijder speeldag", class_="danger-button"
                    ),
                    class_="history-header",
                ),
                ui.div(*tables, class_="history-tables"),
                class_="history-day",
            )
        )
        if played_dates and play_date == played_dates[0]:
            sections.insert(len(sections) - 1, ui.h2("Gespeelde dagen", class_="history-section-title"))
    return ui.div(*sections)


players = sorted(load_all_players(ALL_PLAYERS_FILE), key=str.casefold)
history_choices = _history_dates()

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.title("Manillen | Speeldagen"),
        ui.tags.style(
            """
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
            :root { --ink:#18232b; --muted:#64747c; --paper:#f4f1ea; --panel:#fffdf8; --teal:#137b73; --gold:#e7a83e; --red:#b54d43; --line:#d9d7cc; }
            * { box-sizing:border-box; } body { margin:0; background:radial-gradient(circle at 90% 0%, #dbeae2 0, transparent 30%), var(--paper); color:var(--ink); font-family:'DM Sans', sans-serif; }
            h1,h2,h3 { font-family:'Space Grotesk', sans-serif; } .app-shell { max-width:1180px; margin:0 auto; padding:44px 24px 72px; }
            .eyebrow { color:var(--teal); font-weight:700; letter-spacing:.12em; text-transform:uppercase; font-size:.75rem; } .intro { margin-bottom:28px; }
            .intro h1 { font-size:clamp(2.2rem, 5vw, 4.4rem); line-height:.98; max-width:700px; margin:9px 0 14px; } .intro p { color:var(--muted); max-width:650px; font-size:1.05rem; }
            .nav-tabs { border-bottom:1px solid var(--line); margin-bottom:24px; } .nav-tabs .nav-link { color:var(--muted); font-weight:700; } .nav-tabs .nav-link.active { color:var(--teal); border-color:var(--teal); background:transparent; }
            .panel { background:rgba(255,253,248,.84); border:1px solid var(--line); padding:24px; margin-bottom:20px; box-shadow:0 12px 35px rgba(24,35,43,.05); }
            .panel h2 { margin-top:0; } .form-group { margin-bottom:18px; } label { font-weight:700; }
            .player-selector { position:relative; margin:18px 0 24px; } .player-selector > label { display:block; margin-bottom:8px; }
            #player-search { width:100%; border:1px solid var(--line); border-radius:3px; padding:12px 14px; font-size:1rem; background:#fff; color:var(--ink); }
            #player-search:focus { outline:3px solid rgba(19,123,115,.18); border-color:var(--teal); } .player-suggestions { position:absolute; z-index:10; top:76px; left:0; right:0; max-height:230px; overflow:auto; background:#fff; border:1px solid var(--line); box-shadow:0 10px 25px rgba(24,35,43,.12); } .player-suggestions[hidden] { display:none; }
            .player-suggestion { display:block; width:100%; border:0; border-bottom:1px solid #eee; background:#fff; text-align:left; padding:11px 14px; color:var(--ink); cursor:pointer; } .player-suggestion:hover { background:#e7f1ed; color:var(--teal); } .suggestion-empty { padding:12px 14px; color:var(--muted); font-style:italic; }
            .selected-player-chips { display:flex; flex-wrap:wrap; gap:8px; min-height:46px; padding:14px 0 8px; } .selection-chip { display:inline-flex; align-items:center; gap:7px; padding:6px 9px 6px 12px; border-radius:999px; background:#e6f0ec; border:1px solid #c8ddd5; } .selection-chip button { border:0; background:transparent; color:var(--teal); font-size:1.1rem; line-height:1; cursor:pointer; padding:0 2px; }
            .selector-footer { display:flex; justify-content:space-between; align-items:center; gap:12px; color:var(--muted); font-size:.9rem; } .clear-players { border:0; background:transparent; color:var(--red); padding:4px 0; cursor:pointer; }
            .btn-primary { background:var(--teal); border-color:var(--teal); } .btn-primary:hover { background:#0c625c; border-color:#0c625c; } .btn-success { background:var(--gold); border-color:var(--gold); color:var(--ink); }
            .status { padding:12px 14px; margin:14px 0; border-left:4px solid var(--teal); background:#e7f1ed; } .error-status { border-color:var(--red); background:#f8e7e3; color:#7e2f2a; }
            .tables-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; } .table-card { background:var(--panel); border:1px solid var(--line); padding:16px; }
            .table-title,.history-table-title { font-family:'Space Grotesk'; font-weight:700; margin-bottom:13px; } .score-label { color:var(--teal); font-weight:700; margin-bottom:12px; }
            .player-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; } .player-chip { background:#e6f0ec; border:1px solid #c8ddd5; padding:10px 8px; min-height:42px; display:flex; align-items:center; font-weight:500; }
            .player-chip.reserve { background:#fff0cf; border-color:#ecd49b; color:#805d1d; } .configuration { margin-top:18px; } .alternative { border-top:1px solid var(--line); padding-top:18px; margin-top:22px; }
            .history-day { border-top:1px solid var(--line); padding:22px 0; } .history-header { display:flex; justify-content:space-between; align-items:center; gap:12px; } .history-header h3 { margin:0 0 14px; }
            .history-tables { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; } .history-table { border-left:3px solid var(--gold); padding:10px 12px; background:#fffaf0; } .scores-button { color:var(--teal); border-color:var(--teal); background:transparent; }
            .history-players { color:var(--muted); } .danger-button { color:var(--red); border-color:#dfaaa4; background:transparent; } .empty-state { color:var(--muted); padding:18px 0; }
            .pairings-table { width:100%; border-collapse:collapse; background:var(--panel); } .pairings-table th, .pairings-table td { text-align:left; padding:11px 13px; border-bottom:1px solid var(--line); } .pairings-table th { color:var(--teal); font-family:'Space Grotesk'; } .pairings-table .pair-count { font-weight:700; text-align:right; } .pairings-table th:last-child { text-align:right; }
            .score-table-card { border-top:1px solid var(--line); padding:20px 0; } .score-table-card h3 { margin-top:0; } .score-game { display:grid; grid-template-columns:70px minmax(140px,1fr) 100px 32px 100px minmax(140px,1fr); align-items:center; gap:12px; padding:12px; background:#fffaf0; margin:8px 0; } .score-game .form-group { margin:0; } .score-game-title { font-family:'Space Grotesk'; font-weight:700; } .score-team { font-weight:500; } .score-vs { color:var(--muted); text-align:center; font-weight:700; } .score-warning { color:#805d1d; background:#fff0cf; padding:9px 12px; margin-top:12px; } .score-error { color:#7e2f2a; background:#f8e7e3; padding:10px 12px; margin:12px 0; }
            @media (max-width:760px) { .score-game { grid-template-columns:1fr 1fr; } .score-game-title { grid-column:1 / -1; } .score-vs { display:none; } }
            @media (max-width:600px) { .app-shell { padding:28px 14px 50px; } .panel { padding:17px; } .history-header { align-items:flex-start; flex-direction:column; } }
            """
        )
    ),
    ui.div(
        ui.div("MANILLEN / SPEELDAGEN", class_="eyebrow"),
        ui.h1("Maak ruimte voor nieuwe partners."),
        ui.p("Plan tafels, bewaar de speeldag en houd bij wie al met wie speelde."),
        class_="intro",
    ),
    ui.navset_tab(
        ui.nav_panel(
            "Nieuwe speeldag",
            ui.div(
                ui.input_date("play_date", "Speeldatum", value=date.today()),
                player_selector(players, selected=players),
                ui.input_action_button("generate", "Genereer indeling", class_="btn-primary"),
                ui.input_select(
                    "configuration_choice",
                    "Indeling bekijken en bewaren",
                    {"0": "Beste indeling"},
                    selected="0",
                ),
                ui.output_ui("generation_status"),
                ui.output_ui("configurations"),
                ui.input_action_button("confirm", "Bevestig en bewaar", class_="btn-success"),
                class_="panel",
            ),
        ),
        ui.nav_panel(
            "Scorebladen",
            ui.div(
                ui.h2("Scorebladen"),
                ui.p("Maak scorebladen voor een bestaande of net opgeslagen speeldag."),
                ui.input_select("score_date", "Speeldag", history_choices or {"": "Geen historiek beschikbaar"}),
                ui.layout_columns(
                    ui.output_ui("reserve_fields"),
                ),
                ui.output_ui("reserve_controls"),
                ui.input_action_button("make_scorebladen", "Genereer scorebladen", class_="btn-primary"),
                ui.output_ui("scoreblad_status"),
                ui.download_button("download_scorebladen", "Download scorebladen"),
                class_="panel",
            ),
        ),
        ui.nav_panel(
            "Scores invoeren",
            ui.div(
                ui.h2("Scores invoeren"),
                ui.input_select("score_entry_date", "Speeldag", history_choices or {"": "Geen historiek beschikbaar"}),
                ui.output_ui("score_entry_tables"),
                ui.output_ui("score_validation"),
                ui.input_action_button("save_scores", "Scores opslaan", class_="btn-success"),
                ui.output_ui("score_entry_status"),
                class_="panel",
            ),
        ),
        ui.nav_panel(
            "Tussenstand",
            ui.div(
                ui.h2("Tussenstand"),
                ui.input_select("standings_date", "Periode", {"": "Alle speeldagen (cumulatief)", **{item: item for item in history_choices}}),
                ui.output_ui("standings"),
                class_="panel",
            ),
        ),
        ui.nav_panel(
            "Geschiedenis",
            ui.div(
                ui.h2("Speeldagen"),
                ui.input_action_button("publish_mirror", "Publiceer data", class_="btn-primary"),
                ui.output_ui("publish_status"),
                ui.output_ui("history"),
                class_="panel",
            ),
        ),
        ui.nav_panel(
            "Paringen",
            ui.div(
                ui.h2("Paringen"),
                ui.p("Overzicht van hoe vaak elke combinatie al samen speelde."),
                ui.input_selectize(
                    "pairing_player",
                    "Filter op speler",
                    choices={"": "Alle spelers", **{player: player for player in players}},
                    selected="",
                    options={"placeholder": "Typ een naam...", "allowEmptyOption": True},
                ),
                ui.output_ui("pairings"),
                class_="panel",
            ),
        ),
        id="tabs",
    ),
    class_="app-shell",
)


def server(input: Inputs, output: Outputs, session: Session):
    configuration_state = reactive.Value[list[tuple[int, list[tuple[str, ...]]]]]([])
    selected_config = reactive.Value[int | None](None)
    generation_message = reactive.Value[tuple[str, str] | None](None)
    scoreblad_path = reactive.Value[str | None](None)
    history_refresh = reactive.Value(0)
    score_refresh = reactive.Value(0)
    score_message = reactive.Value[tuple[str, str] | None](None)
    publish_message = reactive.Value[tuple[str, str] | None](None)
    publish_running = reactive.Value(False)
    reserve_message = reactive.Value[tuple[str, str] | None](None)
    delete_clicks = reactive.Value[dict[str, int]]({})
    pending_delete = reactive.Value[str | None](None)

    @reactive.effect
    @reactive.event(input.generate)
    def generate_config():
        selected = list(input.selected_players() or [])
        try:
            if not selected:
                raise ValueError("Selecteer minstens één speler.")
            pool, _, _ = create_player_pool(selected)
            results = make_groups_greedy(pool, 4, str(CSV_PAIRINGS), max_configs=5)
            if not results:
                raise ValueError("Er kon geen geldige indeling worden gevonden.")
            configuration_state.set(results)
            selected_config.set(0)
            ui.update_select(
                "configuration_choice",
                choices={
                    str(index): ("Beste indeling" if index == 0 else f"Alternatief {index}")
                    + f" (score {score})"
                    for index, (score, _) in enumerate(results)
                },
                selected="0",
            )
            generation_message.set(("success", f"{len(results)} indelingen gevonden. De beste staat bovenaan."))
        except Exception as error:
            configuration_state.set([])
            selected_config.set(None)
            generation_message.set(("error", str(error)))

    @render.ui
    def generation_status():
        message = generation_message()
        if not message:
            return ui.HTML("")
        kind, text = message
        return ui.div(text, class_=f"status {'error-status' if kind == 'error' else ''}")

    @render.ui
    def configurations():
        results = configuration_state()
        if not results:
            return ui.HTML("")
        index = selected_config() or 0
        index = index if index < len(results) else 0
        score, config = results[index]
        return _table_cards(config, score)

    @reactive.effect
    @reactive.event(input.configuration_choice)
    def choose_configuration():
        value = input.configuration_choice()
        if value is not None and configuration_state():
            selected_config.set(int(value))

    @reactive.effect
    @reactive.event(input.confirm)
    def request_confirmation():
        results = configuration_state()
        if not results:
            generation_message.set(("error", "Genereer eerst een indeling."))
            return
        ui.modal_show(
            ui.modal(
                ui.h4("Speeldag bewaren?"),
                ui.p(f"De indeling wordt opgeslagen voor {input.play_date()} en de paartellingen worden bijgewerkt."),
                ui.div(
                    ui.input_action_button("confirm_save", "Ja, bewaar", class_="btn-success"),
                    ui.input_action_button("cancel_save", "Annuleren"),
                    class_="d-flex gap-2",
                ),
                easy_close=False,
            )
        )

    @reactive.effect
    @reactive.event(input.cancel_save)
    def cancel_save():
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.confirm_save)
    def save_config():
        try:
            _, config = configuration_state()[selected_config() or 0]
            update_pairs_in_csv(config, str(CSV_PAIRINGS), history_filename=str(HISTORY_FILE), play_date=input.play_date())
            generation_message.set(("success", f"Speeldag {input.play_date()} is bewaard."))
            history_refresh.set(history_refresh() + 1)
            ui.modal_remove()
        except Exception as error:
            generation_message.set(("error", f"Opslaan mislukt: {error}"))

    @render.ui
    def history():
        history_refresh()
        return _history_cards()

    @reactive.effect
    @reactive.event(input.score_navigation)
    def scores_navigation():
        play_date = input.score_navigation()
        ui.update_select("score_entry_date", selected=play_date)
        ui.update_navset("tabs", selected="Scores invoeren")

    @render.ui
    def publish_status():
        message = publish_message()
        if not message:
            return ui.HTML("")
        kind, text = message
        return ui.div(text, class_=f"status {'error-status' if kind == 'error' else ''}")

    @reactive.effect
    @reactive.event(input.publish_mirror)
    async def publish_mirror():
        if publish_running():
            return
        publish_running.set(True)
        publish_message.set(("running", "Publiceren..."))
        ui.update_action_button("publish_mirror", label="Publiceren...", disabled=True)
        try:
            await asyncio.to_thread(trigger_mirror_workflow)
            publish_message.set((
                "success",
                "Publicatie gestart. GitHub Actions verwerkt de update.",
            ))
        except GitHubPublishError as error:
            publish_message.set(("error", str(error)))
        except Exception:
            publish_message.set((
                "error",
                "GitHub-publicatie mislukt door een onverwachte fout.",
            ))
        finally:
            publish_running.set(False)
            ui.update_action_button("publish_mirror", label="Publiceer data", disabled=False)

    @render.ui
    def pairings():
        history_refresh()
        return _pairings_table(input.pairing_player() or None)

    @render.ui
    def score_entry_tables():
        history_refresh()
        score_refresh()
        return _score_entry_tables(input.score_entry_date())

    @render.ui
    def score_validation():
        history_refresh()
        warnings = []
        for table_text, _ in _read_history().get(input.score_entry_date(), []):
            table = int(table_text)
            for game in range(1, 4):
                team1 = getattr(input, _score_input_id(table, game, "team1"))()
                team2 = getattr(input, _score_input_id(table, game, "team2"))()
                if team1 is not None and team2 is not None and team1 < 101 and team2 < 101:
                    warnings.append(f"Tafel {table}, spel {game}: geen van beide scores is 101 of hoger.")
        if not warnings:
            return ui.HTML("")
        return ui.div(*warnings, class_="score-warning")

    @reactive.effect
    @reactive.event(input.save_scores)
    def save_all_scores():
        play_date = input.score_entry_date()
        history = _read_history().get(play_date, [])
        try:
            all_table_scores = []
            for table_text, table_players in history:
                table = int(table_text)
                games = []
                for game, (team1, team2) in enumerate(
                    get_matchups_for_table(table_players), start=1
                ):
                    team1_score = getattr(input, _score_input_id(table, game, "team1"))()
                    team2_score = getattr(input, _score_input_id(table, game, "team2"))()
                    if team1_score is None or team2_score is None:
                        raise ValueError(f"Vul alle 3 scores in voor tafel {table}.")
                    if team1_score < 0 or team2_score < 0 or int(team1_score) != team1_score or int(team2_score) != team2_score:
                        raise ValueError(f"Scores voor tafel {table} moeten niet-negatieve gehele getallen zijn.")
                    games.append({
                        "team1": team1, "team2": team2,
                        "team1_score": int(team1_score), "team2_score": int(team2_score),
                    })
                all_table_scores.append((table, games))
            for table, games in all_table_scores:
                save_scores(play_date, table, games, str(SCORES_FILE))
            score_refresh.set(score_refresh() + 1)
            score_message.set(("success", f"Scores voor {play_date} zijn opgeslagen."))
        except Exception as error:
            score_message.set(("error", str(error)))

    @render.ui
    def score_entry_status():
        message = score_message()
        if not message:
            return ui.HTML("")
        kind, text = message
        return ui.div(text, class_=f"status {'error-status' if kind == 'error' else ''}")

    @render.ui
    def standings():
        score_refresh()
        selected_date = input.standings_date() or None
        return _standings_table(selected_date)

    @reactive.effect
    def delete_handlers():
        history_refresh()
        clicks = delete_clicks()
        for play_date in _history_dates():
            button = getattr(input, _delete_input_id(play_date))
            current = button() or 0
            if current > clicks.get(play_date, 0):
                delete_clicks.set({**clicks, play_date: current})
                pending_delete.set(play_date)
                ui.modal_show(
                    ui.modal(
                        ui.h4("Speeldag verwijderen?"),
                        ui.p(
                            f"Weet je zeker dat je speeldag {play_date} wil verwijderen? "
                            "Dit decrementeert ook de paartellingen."
                        ),
                        ui.div(
                            ui.input_action_button("confirm_delete", "Ja, verwijder", class_="danger-button"),
                            ui.input_action_button("cancel_delete", "Annuleren"),
                            class_="d-flex gap-2",
                        ),
                        easy_close=False,
                    )
                )

    @reactive.effect
    @reactive.event(input.cancel_delete)
    def cancel_delete():
        pending_delete.set(None)
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.confirm_delete)
    def confirm_delete():
        play_date = pending_delete()
        if not play_date:
            return
        try:
            delete_pairings_by_date(
                play_date,
                csv_filename=str(CSV_PAIRINGS),
                history_filename=str(HISTORY_FILE),
            )
            history_refresh.set(history_refresh() + 1)
            ui.update_select("score_date", choices=_history_dates(), selected=None)
        except Exception as error:
            generation_message.set(("error", f"Verwijderen mislukt: {error}"))
        finally:
            pending_delete.set(None)
            ui.modal_remove()

    def current_reserve_assignments(play_date):
        count = required_reserve_count(play_date, str(HISTORY_FILE))
        assignments = {}
        for slot_number in range(1, count + 1):
            reader = getattr(input, f"reserve{slot_number}", None)
            value = reader() if reader else None
            if value and value.strip():
                assignments[f"Reserve {slot_number}"] = value.strip()
        return assignments

    def reserve_count_for_date(play_date):
        return required_reserve_count(play_date, str(HISTORY_FILE)) if play_date else 0

    @render.ui
    def reserve_fields():
        play_date = input.score_date()
        count = reserve_count_for_date(play_date)
        if count == 0:
            return ui.HTML("")
        existing = get_reserve_assignments(play_date, RESERVE_ASSIGNMENTS_FILE)
        fields = [
            ui.input_text(
                f"reserve{slot_number}",
                f"Reserve {slot_number} vervangen door",
                value=existing.get(f"Reserve {slot_number}", ""),
                placeholder="Optioneel",
            )
            for slot_number in range(1, count + 1)
        ]
        return ui.div(*fields, class_="reserve-fields")

    @render.ui
    def reserve_controls():
        play_date = input.score_date()
        if reserve_count_for_date(play_date) == 0:
            return ui.HTML("")
        return ui.div(
            ui.input_action_button("save_reserve_names", "Bewaar reservenamen"),
            ui.output_ui("reserve_status"),
        )

    @reactive.effect
    @reactive.event(input.save_reserve_names)
    def save_reserve_names():
        play_date = input.score_date()
        try:
            if not play_date:
                raise ValueError("Kies eerst een speeldag.")
            save_reserve_assignments(
                play_date,
                current_reserve_assignments(play_date),
                RESERVE_ASSIGNMENTS_FILE,
            )
            history_refresh.set(history_refresh() + 1)
            reserve_message.set(("success", f"Reservenamen voor {play_date} zijn opgeslagen."))
        except Exception as error:
            reserve_message.set(("error", str(error)))

    @render.ui
    def reserve_status():
        message = reserve_message()
        if not message:
            return ui.HTML("")
        kind, text = message
        return ui.div(text, class_=f"status {'error-status' if kind == 'error' else ''}")

    @reactive.effect
    @reactive.event(input.make_scorebladen)
    def create_scorebladen():
        try:
            if not input.score_date():
                raise ValueError("Kies eerst een speeldag.")
            play_date = input.score_date()
            save_reserve_assignments(
                play_date,
                current_reserve_assignments(play_date),
                RESERVE_ASSIGNMENTS_FILE,
            )
            history_refresh.set(history_refresh() + 1)
            scoreblad_path.set(
                fill_scorebladen_from_history(
                    play_date=play_date,
                    history_filename=str(HISTORY_FILE),
                    template_filename=str(SCOREBLAD_TEMPLATE),
                    output_dir=str(SCOREBLAD_OUTPUT_DIR),
                    reserve1=get_reserve_assignments(play_date, RESERVE_ASSIGNMENTS_FILE).get("Reserve 1"),
                    reserve2=get_reserve_assignments(play_date, RESERVE_ASSIGNMENTS_FILE).get("Reserve 2"),
                    reserve3=get_reserve_assignments(play_date, RESERVE_ASSIGNMENTS_FILE).get("Reserve 3"),
                )
            )
        except Exception as error:
            scoreblad_path.set(f"ERROR: {error}")

    @render.ui
    def scoreblad_status():
        path = scoreblad_path()
        if not path:
            return ui.HTML("")
        if path.startswith("ERROR:"):
            return ui.div(path, class_="status error-status")
        return ui.div(f"Gemaakt: {Path(path).name}", class_="status")

    @render.download(
        filename=lambda: Path(
            scoreblad_path()
            or _scoreblad_file_for_date(input.score_date())
            or "scorebladen.xlsx"
        ).name
    )
    async def download_scorebladen():
        path = scoreblad_path() or _scoreblad_file_for_date(input.score_date())
        if path and not (isinstance(path, str) and path.startswith("ERROR:")) and Path(path).exists():
            yield Path(path).read_bytes()


app = App(app_ui, server)