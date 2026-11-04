const routeLabels = {
  seizoenen: "Seizoenen",
  "hall-of-fame": "Hall of Fame",
  tussenstand: "Tussenstand",
  speeldagen: "Speeldagen",
  scores: "Scores",
  parenhistoriek: "Parenhistoriek",
  speler: "Speler",
};

const elements = {
  heading: document.querySelector("#view-heading"),
  kicker: document.querySelector("#view-kicker"),
  build: document.querySelector("#build-label"),
  controls: document.querySelector("#view-controls"),
  content: document.querySelector("#view-content"),
  navigation: document.querySelector("#primary-navigation"),
  menu: document.querySelector("#navigation-toggle"),
  themeToggle: document.querySelector("#theme-toggle"),
  themeIcon: document.querySelector("#theme-icon"),
  themeLabel: document.querySelector("#theme-label"),
  themeColor: document.querySelector('meta[name="theme-color"]'),
};

const themeStorageKey = "manillen-theme";
let manifest;
let players = [];
let pairings = [];
let hallOfFame = [];
const seasonCache = new Map();
let activeRender = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function cell(label, value, className = "", icon = "") {
  const node = element("td", undefined, className);
  if (icon) {
    const marker = element("span", icon, "rank-emoji");
    marker.setAttribute("aria-hidden", "true");
    node.append(marker);
  }
  node.append(document.createTextNode(String(value)));
  node.dataset.label = label;
  return node;
}

function playerSlug(name) {
  return String(name || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("nl")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "speler";
}

function playerLink(name, className = "player-name-link") {
  const link = element("a", String(name), className);
  link.href = `#/speler/${playerSlug(name)}`;
  return link;
}

function playerCell(label, value, className = "", icon = "") {
  const node = cell(label, "", className, icon);
  node.replaceChildren(playerLink(value));
  return node;
}

function table(headers, rows, className = "data-table", rowClasses = [], headerClasses = []) {
  const root = element("table", undefined, className);
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const [index, header] of headers.entries()) {
    const item = element("th", header, headerClasses[index] || "");
    item.scope = "col";
    headRow.append(item);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const [index, values] of rows.entries()) {
    const row = document.createElement("tr");
    if (rowClasses[index]) row.className = rowClasses[index];
    row.append(...values);
    body.append(row);
  }
  root.append(head, body);
  const scrollRegion = element("div", undefined, "table-scroll");
  scrollRegion.setAttribute("role", "region");
  scrollRegion.setAttribute("aria-label", "Tabel, horizontaal verschuifbaar");
  scrollRegion.tabIndex = 0;
  scrollRegion.append(root);
  return scrollRegion;
}

function emptyState(message) {
  return element("p", message, "empty-state");
}

function amsterdamDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Amsterdam",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const dateParts = Object.fromEntries(
    parts.map(({ type, value }) => [type, value]),
  );
  return `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
}

function playdayHasPassed(playDate, now = new Date()) {
  return /^\d{4}-\d{2}-\d{2}$/.test(playDate)
    && playDate < amsterdamDate(now);
}

function nextAmsterdamMidnight(now = new Date()) {
  const [year, month, day] = amsterdamDate(now).split("-").map(Number);
  const nextDate = new Date(Date.UTC(year, month - 1, day + 1));
  const target = {
    year: nextDate.getUTCFullYear(),
    month: nextDate.getUTCMonth() + 1,
    day: nextDate.getUTCDate(),
  };
  const desiredUtc = Date.UTC(target.year, target.month - 1, target.day);
  let timestamp = desiredUtc;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Amsterdam",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(new Date(timestamp));
    const localParts = Object.fromEntries(
      parts.map(({ type, value }) => [type, Number(value)]),
    );
    const localAsUtc = Date.UTC(
      localParts.year,
      localParts.month - 1,
      localParts.day,
      localParts.hour,
      localParts.minute,
      localParts.second,
    );
    const adjustment = desiredUtc - localAsUtc;
    timestamp += adjustment;
    if (adjustment === 0) break;
  }
  return new Date(timestamp);
}

let observedAmsterdamDate = amsterdamDate();
function scheduleAmsterdamDateRefresh() {
  const delay = Math.max(
    0,
    nextAmsterdamMidnight().getTime() - Date.now(),
  );
  window.setTimeout(() => {
    const currentDate = amsterdamDate();
    if (currentDate !== observedAmsterdamDate) {
      observedAmsterdamDate = currentDate;
      if (routeFromHash().route === "speeldagen") renderRoute();
    }
    scheduleAmsterdamDateRefresh();
  }, delay);
}
scheduleAmsterdamDateRefresh();

function setContent(node) {
  elements.content.replaceChildren(node);
  elements.content.setAttribute("aria-busy", "false");
}

function setLoading() {
  const state = element("div", undefined, "loading-state");
  const indicator = element("span", undefined, "loading-indicator");
  indicator.setAttribute("aria-hidden", "true");
  state.append(indicator, element("p", "Gegevens laden…"));
  elements.content.replaceChildren(state);
  elements.content.setAttribute("aria-busy", "true");
}

function setError(message) {
  setContent(element("p", message, "error-state"));
}

async function fetchJson(path) {
  const response = await fetch(`./data/${path}?v=${encodeURIComponent(manifest.buildId)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`JSON-bestand niet beschikbaar: ${path}`);
  }
  return response.json();
}

async function loadSeason(season) {
  if (!seasonCache.has(season)) {
    const request = fetchJson(`seasons/${encodeURIComponent(season)}.json`)
      .catch((error) => {
        seasonCache.delete(season);
        throw error;
      });
    seasonCache.set(season, request);
  }
  return seasonCache.get(season);
}

function routeFromHash() {
  const hash = window.location.hash.slice(1);
  const [path, query = ""] = hash.split("?", 2);
  const parts = path.replace(/^\/+/, "").split("/").filter(Boolean);
  const route = parts[0] && routeLabels[parts[0]] ? parts[0] : "tussenstand";
  const player = route === "speler" && parts[1] ? decodeURIComponent(parts[1]) : "";
  return {
    route,
    player,
    params: new URLSearchParams(query),
  };
}

function routeHash(route, params) {
  const query = params.toString();
  return `#/${route}${query ? `?${query}` : ""}`;
}

function updateFilter(name, value, currentRoute, currentParams) {
  const params = new URLSearchParams(currentParams);
  if (value) params.set(name, value);
  else params.delete(name);
  if (name === "seizoen") params.delete("datum");
  const hash = routeHash(currentRoute, params);
  if (hash === window.location.hash) renderRoute();
  else window.location.hash = hash;
}

function replaceSearchFilter(name, value, route, params) {
  const nextParams = new URLSearchParams(params);
  if (value) nextParams.set(name, value);
  else nextParams.delete(name);
  window.history.replaceState(null, "", routeHash(route, nextParams));
}

function selectControl(label, name, options, selected, onChange) {
  const field = element("label", undefined, "filter-field");
  field.append(element("span", label));
  const select = document.createElement("select");
  select.name = name;
  for (const [value, text] of options) {
    const option = element("option", text);
    option.value = value;
    option.selected = value === selected;
    select.append(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  field.append(select);
  return field;
}

function searchControl(label, value, placeholder, onInput) {
  const field = element("label", undefined, "filter-field");
  field.append(element("span", label));
  const input = document.createElement("input");
  input.type = "search";
  input.value = value;
  input.placeholder = placeholder;
  input.autocomplete = "off";
  input.addEventListener("input", () => onInput(input.value));
  field.append(input);
  return field;
}

function seasonOptions(includeAll = true) {
  const options = [];
  if (includeAll) options.push(["all", "Alle seizoenen"]);
  for (const season of [...manifest.seasons].sort(
    (left, right) => right.seasonNumber - left.seasonNumber,
  )) {
    options.push([season.season, `S${season.seasonNumber} · ${season.season}`]);
  }
  return options;
}

function chosenSeason(params, includeAll = true) {
  const selected = params.get("seizoen");
  return selected && ((includeAll && selected === "all") || manifest.seasons.some(
    (season) => season.season === selected,
  ))
    ? selected
    : manifest.activeSeason;
}

function updateNavigation(activeRoute) {
  for (const link of elements.navigation.querySelectorAll("a[data-route]")) {
    if (link.dataset.route === activeRoute) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

function closeNavigation(returnFocus = false) {
  elements.navigation.classList.remove("is-open");
  elements.menu.setAttribute("aria-expanded", "false");
  elements.menu.setAttribute("aria-label", "Open navigatie");
  if (returnFocus) elements.menu.focus();
}

function setTheme(isDark, persist = false) {
  const theme = isDark ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
  elements.themeToggle.setAttribute("aria-pressed", String(isDark));
  elements.themeToggle.setAttribute(
    "aria-label",
    `Schakel naar ${isDark ? "licht" : "donker"} thema`,
  );
  elements.themeIcon.textContent = isDark ? "☀️" : "🌙";
  elements.themeLabel.textContent = isDark ? "Licht" : "Donker";
  elements.themeColor.content = isDark ? "#171c19" : "#f4f1ea";

  if (persist) {
    try {
      window.localStorage.setItem(themeStorageKey, theme);
    } catch (error) {
      console.warn("Thema-voorkeur kon niet worden opgeslagen.", error);
    }
  }
}

function loadTheme() {
  try {
    return window.localStorage.getItem(themeStorageKey) === "dark";
  } catch (error) {
    console.warn("Thema-voorkeur kon niet worden gelezen.", error);
    return false;
  }
}

function standingsView(data, route, params) {
  const currentSeason = chosenSeason(params, false);
  const selectedDate = params.get("datum") || "";
  const dateOptions = [["", "Alle speeldagen"]];
  for (const day of data.playdays) dateOptions.push([day.date, day.date]);
  const validDate = dateOptions.some(([value]) => value === selectedDate)
    ? selectedDate
    : "";
  elements.controls.replaceChildren(
    selectControl("Seizoen", "seizoen", seasonOptions(false), currentSeason, (value) => {
      updateFilter("seizoen", value, route, params);
    }),
    selectControl(
      "Speeldag",
      "datum",
      dateOptions,
      validDate,
      (value) => updateFilter("datum", value, route, params),
    ),
  );
  let rows = data.standings;
  if (validDate) {
    rows = data.playdays.find((day) => day.date === validDate)?.standings || [];
  }
  if (!rows.length) return emptyState("Nog geen scores gevonden.");
  const medalClasses = ["rank-gold", "rank-silver", "rank-bronze"];
  const medalEmojis = ["🥇", "🥈", "🥉"];
  const activeIndices = rows
    .map((row, index) => (row.gamesPlayed > 0 ? index : -1))
    .filter((index) => index >= 0);
  const lastActiveIndex = activeIndices.length ? activeIndices[activeIndices.length - 1] : -1;
  const bodyRows = rows.map((row, index) => [
    cell("#", index + 1, "numeric"),
    playerCell("Speler", row.player, "", medalEmojis[index] || (index === lastActiveIndex ? "🏮" : "")),
    cell("Gewonnen", row.wins, "numeric"),
    cell("Gespeeld", row.gamesPlayed, "numeric"),
    cell("Voor", row.pointsFor, "numeric"),
    cell("Tegen", row.pointsAgainst, "numeric"),
    cell("Saldo", row.pointDiff, "numeric"),
  ]);
  const rowClasses = rows.map((_, index) => (
    medalClasses[index] || (index === lastActiveIndex ? "rank-lantern" : "")
  ));
  const root = element("div");
  root.append(table(
    ["#", "Speler", "Gewonnen", "Gespeeld", "Voor", "Tegen", "Saldo"],
    bodyRows,
    "data-table",
    rowClasses,
  ));
  root.append(element("p", "* = reservespeler.", "reserve-footnote"));
  return root;
}

function playdaysView(data, route, params) {
  const selectedSeason = chosenSeason(params);
  elements.controls.replaceChildren(
    selectControl("Seizoen", "seizoen", seasonOptions(), selectedSeason, (value) => {
      updateFilter("seizoen", value, route, params);
    }),
  );
  if (!data.playdays.length) return emptyState("Nog geen speeldagen gevonden.");
  const fragment = document.createDocumentFragment();
  for (const day of data.playdays) {
    const showResults = playdayHasPassed(day.date);
    const card = element("section", undefined, "day-card");
    const title = element("h3", day.date);
    if (day.location) {
      title.append(element("span", ` · ${day.location}`));
    }
    card.append(title);
    for (const tableData of day.tables) {
      const tableCard = element("section", undefined, "table-card");
      tableCard.append(element("h3", `Tafel ${tableData.table}`));
      const names = element("ul", undefined, "player-list");
      const hasResults = tableData.standings.some(
        ({ wins, losses }) => wins + losses > 0,
      );
      if (!showResults || !hasResults) {
        names.setAttribute("aria-label", "Spelers aan tafel");
        for (const player of tableData.players) {
          const row = element("li", undefined, "player-result-row");
          row.append(playerLink(player, "player-result-name"));
          names.append(row);
        }
        tableCard.append(names);
        tableCard.append(emptyState(
          showResults
            ? "Nog geen scores voor deze tafel."
            : day.date === amsterdamDate()
              ? "W-L-resultaten verschijnen na afloop van vandaag."
              : "W-L-resultaten verschijnen na afloop van de speeldag.",
        ));
        card.append(tableCard);
        continue;
      }
      names.setAttribute("aria-label", "W-L-resultaten per speler");
      for (const standing of tableData.standings) {
        const { player, wins, losses } = standing;
        const row = element("li", undefined, "player-result-row");
        row.append(playerLink(player, "player-result-name"));
        const result = element("strong", `${wins}-${losses}`, "player-result-record");
        result.setAttribute("aria-label", `${wins} gewonnen, ${losses} verloren`);
        row.append(result);
        names.append(row);
      }
      tableCard.append(names);
      card.append(tableCard);
    }
    fragment.append(card);
  }
  return fragment;
}

function scoresView(data, route, params) {
  const selectedSeason = chosenSeason(params, false);
  const selectedDate = params.get("datum") || "";
  const playerQuery = params.get("speler") || "";
  const dates = [["", "Alle speeldagen"], ...data.playdays.map((day) => [day.date, day.date])];
  const validDate = dates.some(([value]) => value === selectedDate) ? selectedDate : "";
  const results = element("div");
  const playerFilter = searchControl("Filter op speler", playerQuery, "Typ een naam…", (value) => {
    replaceSearchFilter("speler", value, route, params);
    results.replaceChildren(scoresTable(data, validDate, value));
  });
  elements.controls.replaceChildren(
    selectControl("Seizoen", "seizoen", seasonOptions(false), selectedSeason, (value) => {
      updateFilter("seizoen", value, route, params);
    }),
    selectControl(
      "Speeldag",
      "datum",
      dates,
      validDate,
      (value) => updateFilter("datum", value, route, params),
    ),
    playerFilter,
  );
  results.append(scoresTable(data, validDate, playerQuery));
  return results;
}

function scoresTable(data, selectedDate, playerQuery) {
  const query = playerQuery.trim().toLocaleLowerCase("nl");
  const rows = data.scores.filter((score) => (
    (!selectedDate || score.date === selectedDate)
    && (!query || `${score.team1Players} ${score.team2Players}`.toLocaleLowerCase("nl").includes(query))
  ));
  if (!rows.length) return emptyState("Nog geen scores gevonden.");
  return table(
    ["Datum", "Tafel", "Spel", "Team 1", "Score", "Team 2", "Score"],
    rows.map((row) => {
      const team1Won = row.validScore && row.team1Score > row.team2Score;
      const team2Won = row.validScore && row.team2Score > row.team1Score;
      return [
        cell("Datum", row.date),
        cell("Tafel", row.table, "numeric"),
        cell(
          "Spel",
          row.validScore ? row.game : `${row.game} — ongeldig: gelijke score`,
          row.validScore ? "numeric" : "numeric score-invalid",
        ),
        cell(
          "Team 1",
          row.team1Players.replaceAll("|", " + "),
          !row.validScore ? "" : team1Won ? "score-winner" : "score-loser",
        ),
        cell("Score", row.team1Score, "numeric"),
        cell(
          "Team 2",
          row.team2Players.replaceAll("|", " + "),
          !row.validScore ? "" : team2Won ? "score-winner" : "score-loser",
        ),
        cell("Score", row.team2Score, "numeric"),
      ];
    }),
  );
}

function pairingsView(route, params) {
  const playerQuery = params.get("speler") || "";
  const results = element("div");
  const playerFilter = searchControl("Zoek speler", playerQuery, "Typ een naam…", (value) => {
    replaceSearchFilter("speler", value, route, params);
    results.replaceChildren(pairingsTable(value));
  });
  elements.controls.replaceChildren(playerFilter);
  results.append(pairingsTable(playerQuery));
  return results;
}

function pairingsTable(playerQuery) {
  const query = playerQuery.trim().toLocaleLowerCase("nl");
  const rows = pairings.filter((pair) => (
    pair.count > 0
    && (!query || `${pair.player1} ${pair.player2}`.toLocaleLowerCase("nl").includes(query))
  ));
  if (!rows.length) return emptyState("Geen paringen gevonden.");
  return table(
    ["Speler 1", "Speler 2", "Samen gespeeld"],
    rows.map((row) => [
      cell("Speler 1", row.player1),
      cell("Speler 2", row.player2),
      cell("Samen gespeeld", row.count, "numeric"),
    ]),
  );
}

function seasonsView(seasonData) {
  elements.controls.replaceChildren();
  const rows = [...seasonData]
    .sort(
      (left, right) => right.seasonNumber - left.seasonNumber,
    )
    .map((season) => {
      const item = manifest.seasons.find((row) => row.season === season.season);
      const playdayCell = cell("Speeldagen", "—");
      if (season.playdays.length) {
        const label = season.playdays.length === 1
          ? "Bekijk 1 speeldag"
          : `Bekijk ${season.playdays.length} speeldagen`;
        const link = element("a", label);
        link.href = routeHash(
          "speeldagen",
          new URLSearchParams({ seizoen: season.season }),
        );
        playdayCell.replaceChildren(link);
      }
      return [
        cell("Seizoen", `S${item?.seasonNumber ?? season.seasonNumber}`),
        cell("Label", season.season),
        cell("Pool", item?.poolSize ?? season.poolSize, "numeric"),
        cell("🥇 Goud", season.awards.Gold || "—", "rank-gold"),
        cell("🥈 Zilver", season.awards.Silver || "—", "rank-silver"),
        cell("🥉 Brons", season.awards.Bronze || "—", "rank-bronze"),
        cell("🏮 Rode lantaarn", season.awards.RedLantern || "—", "rank-lantern"),
        playdayCell,
      ];
    });
  if (!rows.length) return emptyState("Nog geen seizoenen gevonden.");
  return table(
    ["Seizoen", "Label", "Pool", "🥇 Goud", "🥈 Zilver", "🥉 Brons", "🏮 Rode lantaarn", "Speeldagen"],
    rows,
    "data-table",
    [],
    ["", "", "", "rank-gold", "rank-silver", "rank-bronze", "rank-lantern"],
  );
}

function hallOfFameView() {
  elements.controls.replaceChildren();
  if (!hallOfFame.length) return emptyState("Nog geen Hall of Fame-resultaten.");
  return table(
    ["Speler", "🥇 Goud", "🥈 Zilver", "🥉 Brons", "🏮 Rode lantaarn"],
    hallOfFame.map((row) => [
      playerCell("Speler", row.Player),
      cell("🥇 Goud", row.Gold, "numeric rank-gold"),
      cell("🥈 Zilver", row.Silver, "numeric rank-silver"),
      cell("🥉 Brons", row.Bronze, "numeric rank-bronze"),
      cell("🏮 Rode lantaarn", row.RedLantern, "numeric rank-lantern"),
    ]),
    "data-table",
    [],
    ["", "rank-gold", "rank-silver", "rank-bronze", "rank-lantern"],
  );
}

async function loadPlayerProfile(slug) {
  const safeSlug = String(slug || "").trim();
  if (!safeSlug) return null;
  try {
    return await fetchJson(`players/${safeSlug}.json`);
  } catch (error) {
    console.warn("Spelersprofiel niet beschikbaar", error);
    return null;
  }
}

function playerProfileView(profile) {
  if (!profile) {
    return emptyState("Speler niet gevonden.");
  }
  const overview = table(
    ["Veld", "Waarde"],
    [
      [cell("Veld", "Speler"), cell("Waarde", profile.name)],
      [cell("Veld", "Gespeeld"), cell("Waarde", profile.gamesPlayed, "numeric")],
      [cell("Veld", "Gewonnen"), cell("Waarde", profile.wins, "numeric")],
      [cell("Veld", "Verloren"), cell("Waarde", profile.losses, "numeric")],
      [cell("Veld", "Winstpercentage"), cell("Waarde", profile.winRate == null ? "n.v.t." : `${(profile.winRate * 100).toFixed(1)}%`)],
      [cell("Veld", "Saldo"), cell("Waarde", profile.pointDiff, "numeric")],
    ],
  );
  const wrapper = element("div", undefined, "player-profile");
  const header = element("h3", profile.name, "player-profile-name");
  wrapper.append(header, overview);
  if (Array.isArray(profile.seasons) && profile.seasons.length) {
    wrapper.append(table(
      ["Seizoen", "Gespeeld", "Gewonnen", "Verloren", "Saldo"],
      profile.seasons.map((season) => [
        cell("Seizoen", season.season),
        cell("Gespeeld", season.gamesPlayed, "numeric"),
        cell("Gewonnen", season.wins, "numeric"),
        cell("Verloren", season.losses, "numeric"),
        cell("Saldo", season.pointDiff, "numeric"),
      ]),
      "data-table",
    ));
  }
  return wrapper;
}

async function renderRoute() {
  const renderId = ++activeRender;
  const { route, player, params } = routeFromHash();
  const routeKey = route;
  updateNavigation(routeKey);
  elements.heading.textContent = routeLabels[routeKey] || "Tussenstand";
  elements.kicker.textContent = routeKey === "speler" ? "SPELERS" : "OVERZICHT";
  closeNavigation();
  setLoading();
  try {
    if (!manifest) {
      throw new Error("Het snapshotmanifest is nog niet geladen.");
    }
    if (route === "speler") {
      const slug = player || params.get("speler") || "";
      const profile = await loadPlayerProfile(slug);
      if (renderId !== activeRender) return;
      setContent(playerProfileView(profile) || emptyState("Speler niet gevonden."));
      return;
    }
    if (route === "seizoenen") {
      const seasonData = await Promise.all(
        manifest.seasons.map((season) => loadSeason(season.season)),
      );
      if (renderId !== activeRender) return;
      setContent(seasonsView(seasonData));
      return;
    }
    if (route === "hall-of-fame") {
      if (!hallOfFame.length) hallOfFame = await fetchJson("hall-of-fame.json");
      if (renderId !== activeRender) return;
      setContent(hallOfFameView());
      return;
    }
    if (route === "parenhistoriek") {
      if (!pairings.length) pairings = await fetchJson("pairings.json");
      if (renderId !== activeRender) return;
      setContent(pairingsView(routeKey, params));
      return;
    }
    const selectedSeason = chosenSeason(
      params,
      route !== "tussenstand" && route !== "scores",
    );
    if (selectedSeason !== params.get("seizoen")) {
      params.set("seizoen", selectedSeason);
      window.history.replaceState(null, "", routeHash(routeKey, params));
    }
    const data = await loadSeason(selectedSeason);
    if (renderId !== activeRender) return;
    if (route === "tussenstand") setContent(standingsView(data, routeKey, params));
    else if (route === "speeldagen") setContent(playdaysView(data, routeKey, params));
    else setContent(scoresView(data, routeKey, params));
  } catch (error) {
    if (renderId === activeRender) {
      setError("De gegevens konden niet worden geladen. Probeer het later opnieuw.");
      console.error(error);
    }
  }
}

async function start() {
  try {
    const response = await fetch("./data/manifest.json");
    if (!response.ok) throw new Error("Het snapshotmanifest is niet beschikbaar.");
    manifest = await response.json();
    if (!manifest.buildId || !manifest.activeSeason || !Array.isArray(manifest.seasons)) {
      throw new Error("Het snapshotmanifest heeft een ongeldig schema.");
    }
    elements.build.textContent = `Snapshot ${manifest.buildId}`;
    if (!window.location.hash) {
      window.history.replaceState(
        null,
        "",
        routeHash("tussenstand", new URLSearchParams({ seizoen: manifest.activeSeason })),
      );
    }
    await renderRoute();
  } catch (error) {
    setError("De gegevens konden niet worden geladen. Probeer het later opnieuw.");
    console.error(error);
  }
}

elements.menu.addEventListener("click", () => {
  const open = elements.navigation.classList.toggle("is-open");
  elements.menu.setAttribute("aria-expanded", String(open));
  elements.menu.setAttribute("aria-label", open ? "Sluit navigatie" : "Open navigatie");
});

setTheme(loadTheme());
elements.themeToggle.addEventListener("click", () => {
  setTheme(document.documentElement.dataset.theme !== "dark", true);
});

elements.navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) closeNavigation();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.navigation.classList.contains("is-open")) {
    closeNavigation(true);
  }
});

document.addEventListener("click", (event) => {
  if (
    elements.navigation.classList.contains("is-open")
    && !elements.navigation.contains(event.target)
    && !elements.menu.contains(event.target)
  ) {
    closeNavigation();
  }
});

window.addEventListener("hashchange", renderRoute);
start();
