(() => {
  "use strict";
  const root = document.querySelector("[data-story-type]");
  if (!root) return;
  const apiUrl = root.dataset.apiUrl;
  const type = root.dataset.storyType;
  const INTERVAL = 5000;
  let timer = null;
  let stopped = false;
  let connectedOnce = false;
  let disconnected = false;
  let clockBase = null;
  let localBase = 0;
  let lastEventOrder = -1;
  let filter = "all";
  const $ = (id) => document.getElementById(id);
  const safeText = (value) => value == null ? "" : String(value);
  const setVisible = (node, visible) => { if (node) node.hidden = !visible; };
  const humanError = "Live-Daten sind vorübergehend nicht erreichbar. Der erneute Verbindungsversuch läuft automatisch.";

  function startClock(serverNow, elapsed) {
    // Use the server's elapsed sample, not the browser's wall clock. Refreshing
    // or reconnecting only resynchronizes; it never restarts from zero.
    const elapsedSeconds = Number(elapsed);
    if (Number.isFinite(elapsedSeconds)) {
      clockBase = elapsedSeconds * 1000;
      localBase = performance.now();
    }
  }
  const currentClock = () => {
    if (clockBase === null) return "—";
    const total = Math.max(0, Math.floor((performance.now() - localBase + clockBase) / 1000));
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
  };
  function showError(id, message) {
    const el = $(id);
    if (!el) return;
    el.textContent = message;
    setVisible(el, true);
  }
  function clearError(id) {
    const el = $(id);
    if (el) { el.textContent = ""; el.classList.remove("is-ok"); setVisible(el, false); }
  }
  function setConnection(connected, statusId) {
    const dot = $("live-dot");
    const status = $(statusId);
    if (dot) dot.classList.toggle("is-offline", !connected);
    if (!status) return;
    status.textContent = connected ? (connectedOnce ? "VERBUNDEN · LIVE" : "LIVE") : "VERBINDUNG UNTERBROCHEN";
    if (!connected) status.style.color = "var(--ls-red)";
    else status.style.color = "";
  }
  function minuteLabel(event) {
    const minute = Number(event.minute);
    const added = Number(event.added);
    if (!Number.isFinite(minute)) return "—";
    return `${Math.trunc(minute)}${Number.isFinite(added) && added > 0 ? `+${Math.trunc(added)}` : ""}′`;
  }
  function filterEvent(event) {
    if (filter === "goals") return event.cls === "goal";
    if (filter === "chances") return Number(event.level) >= 3;
    return true;
  }
  function renderEvent(event) {
    const row = document.createElement("li");
    row.className = "ls-event";
    row.dataset.cls = safeText(event.cls);
    row.dataset.level = String(Math.max(1, Math.min(5, Number(event.level) || 1)));
    row.hidden = !filterEvent(event);
    const minute = document.createElement("time");
    minute.className = "ls-event-minute";
    minute.textContent = minuteLabel(event);
    const body = document.createElement("div");
    body.className = "ls-event-body";
    const meta = document.createElement("div");
    meta.className = "ls-event-meta";
    const kind = document.createElement("span");
    kind.textContent = safeText(event.kind || event.cls || "Ereignis").replaceAll("_", " ");
    meta.appendChild(kind);
    if (event.team === "home" || event.team === "away") {
      const team = document.createElement("span");
      team.className = "ls-event-team";
      team.textContent = event.team === "home" ? "HEIM" : "AUSWÄRTS";
      meta.appendChild(team);
    }
    const weight = document.createElement("span");
    weight.className = "ls-weight";
    weight.setAttribute("aria-label", `Bedeutung ${row.dataset.level} von 5`);
    for (let index = 1; index <= 5; index += 1) {
      const mark = document.createElement("i");
      if (index <= Number(row.dataset.level)) mark.className = "on";
      weight.appendChild(mark);
    }
    meta.appendChild(weight);
    const text = document.createElement("div");
    text.className = "ls-event-text";
    text.textContent = safeText(event.text);
    body.append(meta, text);
    row.append(minute, body);
    return row;
  }
  function updateTicker(data) {
    setConnection(true, "match-status");
    clearError("ticker-alert");
    const score = $("match-score");
    if (score && data.score != null) score.textContent = safeText(data.score);
    const clock = $("match-clock");
    if (clock) {
      startClock(data.server_now, data.elapsed_s);
      clock.textContent = currentClock();
    }
    const progress = $("match-progress");
    const duration = Number(data.duration_s);
    const elapsed = Number(data.elapsed_s);
    if (progress && duration > 0 && Number.isFinite(elapsed)) {
      const pct = Math.min(100, Math.max(0, elapsed / duration * 100));
      progress.style.transform = `scaleX(${pct / 100})`;
    }
    const status = $("match-status");
    if (status && data.released) status.textContent = "SPIELBERICHT FREIGEGEBEN";
    else if (status && data.status === "preparing") status.textContent = "SPIEL WIRD VORBEREITET";
    const subline = $("match-subline");
    if (subline && data.fallback) subline.textContent = "Automatisch gesicherte Live-Erzählung.";
    const list = $("ticker-events");
    if (list && Array.isArray(data.events)) {
      list.querySelectorAll(".ls-skeleton").forEach((skeleton) => skeleton.remove());
      const events = data.events.slice().sort((a, b) => Number(a.order) - Number(b.order));
      for (const event of events) {
        const order = Number(event.order);
        if (!Number.isFinite(order) || order <= lastEventOrder) continue;
        list.appendChild(renderEvent(event));
        lastEventOrder = order;
      }
      const hasAny = list.querySelector(".ls-event:not(.ls-skeleton)");
      setVisible($("ticker-empty"), !hasAny);
    }
    const reportUrl = data.report_url;
    if (data.released) {
      stopped = true;
      const reportContainer = $("report-link");
      if (reportContainer && reportUrl) {
        const anchor = document.createElement("a");
        anchor.href = reportUrl;
        anchor.textContent = "Vollständigen Spielbericht öffnen";
        reportContainer.replaceChildren(anchor);
        setVisible(reportContainer, true);
      } else if ($("report-fallback")) {
        setVisible($("report-fallback"), true);
      }
      if (timer) window.clearTimeout(timer);
    }
  }
  function renderConference(data) {
    const status = $("round-status");
    if (status) {
      status.textContent = data.released ? "SPIELTAG FREIGEGEBEN" : data.complete ? "SPIELTAG LÄUFT" : "SPIELTAG WIRD VORBEREITET";
      status.style.color = data.released ? "var(--ls-green)" : "";
    }
    const pending = $("pending-count");
    if (pending) pending.textContent = safeText(data.pending_count ?? 0);
    const lock = $("round-lock");
    if (lock) {
      lock.textContent = data.released ? "ERGEBNISSE FREIGEGEBEN" : "ERGEBNISSE GESPERRT";
      lock.classList.toggle("is-released", Boolean(data.released));
    }
    startClock(data.server_now, data.elapsed_s);
    if ($("round-clock")) $("round-clock").textContent = currentClock();
    const matches = Array.isArray(data.matches) ? data.matches : [];
    const count = $("match-count");
    if (count) count.textContent = `${matches.length} ${matches.length === 1 ? "Partie" : "Partien"}`;
    const container = $("conference-matches");
    if (!container) return;
    const cards = matches.map((match) => {
      const card = document.createElement("a");
      card.className = "ls-match-card";
      card.href = safeText(match.ticker_url || "#");
      const top = document.createElement("div");
      top.className = "ls-match-card-top";
      const state = document.createElement("span");
      state.className = match.ended ? "ls-match-final" : "ls-match-live";
      state.textContent = match.status === "preparing" ? "STORY WIRD VORBEREITET" :
        match.ended ? (data.released ? "ABGESCHLOSSEN" : "SPIELENDE · GESPERRT") : "LIVE";
      const index = document.createElement("span");
      index.textContent = `SPIEL ${safeText(match.id)}`;
      top.append(state, index);
      const teams = document.createElement("div");
      teams.className = "ls-match-teams";
      const home = document.createElement("span"); home.textContent = safeText(match.home);
      const score = document.createElement("span"); score.className = "ls-match-score"; score.textContent = safeText(match.score || "0:0");
      const away = document.createElement("span"); away.textContent = safeText(match.away);
      teams.append(home, score, away);
      const last = document.createElement("div");
      last.className = "ls-match-last";
      last.textContent = match.last_event ? `${minuteLabel(match.last_event)} · ${safeText(match.last_event.text)}` : "Noch keine Ereignisse";
      card.append(top, teams, last);
      return card;
    });
    container.replaceChildren(...cards);
    setVisible($("conference-empty"), matches.length === 0);
    const note = $("release-note");
    if (note) note.textContent = data.released ? "Der Spieltag ist freigegeben. Öffne eine Partie, um den vollständigen Spielbericht aufzurufen." : "Endberichte werden erst nach Freigabe des gesamten Spieltags verfügbar.";
  }
  async function poll() {
    if (stopped) return;
    try {
      const response = await fetch(apiUrl, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      connectedOnce = true;
      if (type === "conference") setConnection(true, "round-status");
      if (type === "ticker") updateTicker(data);
      else renderConference(data);
      clearError(type === "ticker" ? "ticker-alert" : "conference-alert");
      if (disconnected) {
        const alertId = type === "ticker" ? "ticker-alert" : "conference-alert";
        showError(alertId, "Verbindung wiederhergestellt. Live-Daten werden fortgesetzt.");
        const alert = $(alertId);
        if (alert) alert.classList.add("is-ok");
        window.setTimeout(() => clearError(alertId), 3500);
        disconnected = false;
      }
      if (data.released) stopped = true;
    } catch (error) {
      disconnected = true;
      setConnection(false, type === "ticker" ? "match-status" : "round-status");
      showError(type === "ticker" ? "ticker-alert" : "conference-alert", humanError);
    }
    if (!stopped) timer = window.setTimeout(poll, INTERVAL);
  }
  if (type === "ticker") {
    document.querySelectorAll(".ls-filter button").forEach((button) => {
      button.addEventListener("click", () => {
        filter = button.dataset.filter || "all";
        document.querySelectorAll(".ls-filter button").forEach((candidate) => {
          const active = candidate === button;
          candidate.classList.toggle("is-active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
        document.querySelectorAll("#ticker-events .ls-event:not(.ls-skeleton)").forEach((row) => {
          const level = Number(row.dataset.level || 1);
          row.hidden = filter === "goals" ? row.dataset.cls !== "goal" : filter === "chances" ? level < 3 : false;
        });
        const eventRows = document.querySelectorAll("#ticker-events .ls-event:not(.ls-skeleton)");
        const visible = Array.from(eventRows).some((row) => !row.hidden);
        const empty = $("ticker-empty");
        if (empty) {
          empty.textContent = eventRows.length && !visible ? "Keine Ereignisse in diesem Filter." : "Noch keine Ereignisse. Der Anpfiff steht unmittelbar bevor.";
          setVisible(empty, !visible);
        }
      });
    });
  }
  window.setInterval(() => {
    const clock = $(type === "ticker" ? "match-clock" : "round-clock");
    if (clock && clockBase !== null) clock.textContent = currentClock();
  }, 1000);
  poll();
})();