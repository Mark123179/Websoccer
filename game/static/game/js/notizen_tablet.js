/* Manager-Notizen Tablet — Logik (Vanilla JS, kein Framework).
   Speicherung: standardmäßig localStorage.
   Für Django-Backend: window.NOTIZEN_API_URL = "/api/notizen/" setzen.
   CSRF: Projekt nutzt session-basiertes CSRF (kein Cookie) —
   Token kommt aus window.NOTIZEN_CSRF (im Template gesetzt). */
(function () {
  "use strict";

  var API = window.NOTIZEN_API_URL || null;
  var KEY = "me_manager_notes";
  var notes = [];
  var activeId = null;
  var saveTimer = null;
  var loadFailed = false;   // GET fehlgeschlagen → niemals mit leerer Liste überschreiben
  var dirty = false;        // ungespeicherte Änderung vorhanden (für pagehide-Flush)

  /* ---------- Speicherung ---------- */
  function getCsrf() {
    if (window.NOTIZEN_CSRF) return window.NOTIZEN_CSRF;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  function load(cb) {
    if (API) {
      fetch(API, { credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (data) { loadFailed = false; cb(data.notes || []); })
        .catch(function () { loadFailed = true; cb([]); });
    } else {
      var data = [];
      try { data = JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) {}
      cb(data);
    }
  }
  function doSave(keepalive) {
    dirty = false;
    fetch(API, {
      method: "PUT",
      credentials: "same-origin",
      keepalive: !!keepalive,
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
      body: JSON.stringify({ notes: notes })
    }).catch(function () { dirty = true; });
  }
  function persist() {
    if (API) {
      if (loadFailed) return; // Server-Stand unbekannt → nicht überschreiben
      dirty = true;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () { doSave(false); }, 600); // debounce
    } else {
      try { localStorage.setItem(KEY, JSON.stringify(notes)); } catch (e) {}
    }
  }

  /* ---------- Helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function uid(p) { return p + Date.now() + Math.floor(Math.random() * 1000); }
  function active() { return notes.find(function (n) { return n.id === activeId; }) || null; }
  function touch(n) { n.updatedAt = Date.now(); persist(); }
  function fmtDate(ts) {
    var d = new Date(ts);
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) +
      ", " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr";
  }

  /* ---------- Rendering ---------- */
  function renderList() {
    var list = $("nt-list");
    list.innerHTML = "";
    var sorted = notes.slice().sort(function (a, b) { return b.updatedAt - a.updatedAt; });
    if (!sorted.length) {
      var e = document.createElement("div");
      e.className = "nt-empty";
      e.innerHTML = "Noch keine Notizen.<br>Lege die erste an.";
      list.appendChild(e);
    }
    sorted.forEach(function (n) {
      var item = document.createElement("div");
      item.className = "nt-item" + (n.id === activeId ? " active" : "");
      var done = n.todos.filter(function (t) { return t.done; }).length;
      var firstLine = (n.content || "").split("\n")[0];
      var meta = fmtDate(n.updatedAt).split(",")[0] + (firstLine ? " · " + firstLine : "");
      item.innerHTML =
        '<div class="row"><div class="t"></div>' +
        (n.todos.length ? '<div class="badge">✓ ' + done + "/" + n.todos.length + "</div>" : "") +
        '</div><div class="meta"></div>';
      item.querySelector(".t").textContent = n.title || "Ohne Titel";
      item.querySelector(".meta").textContent = meta;
      item.addEventListener("click", function () { activeId = n.id; render(); });
      list.appendChild(item);
    });
  }

  function renderEditor() {
    var n = active();
    $("nt-editor").hidden = !n;
    $("nt-noselect").hidden = !!n;
    if (!n) return;
    if (document.activeElement !== $("nt-ed-title")) $("nt-ed-title").value = n.title;
    if (document.activeElement !== $("nt-ed-content")) $("nt-ed-content").value = n.content;
    $("nt-ed-date").textContent = "Zuletzt bearbeitet: " + fmtDate(n.updatedAt);

    var list = $("nt-todo-list");
    list.innerHTML = "";
    n.todos.forEach(function (t) {
      var row = document.createElement("div");
      row.className = "nt-todo" + (t.done ? " done" : "");
      row.innerHTML = '<div class="box">' + (t.done ? "✓" : "") + '</div><input><button class="del" type="button">✕</button>';
      var input = row.querySelector("input");
      input.value = t.text;
      row.querySelector(".box").addEventListener("click", function () { t.done = !t.done; touch(n); render(); });
      input.addEventListener("input", function () { t.text = input.value; touch(n); renderList(); });
      row.querySelector(".del").addEventListener("click", function () {
        n.todos = n.todos.filter(function (x) { return x !== t; }); touch(n); render();
      });
      list.appendChild(row);
    });
  }

  function render() { renderList(); renderEditor(); }

  /* ---------- Events ---------- */
  function init() {
    var overlay = $("nt-overlay");
    if (!overlay) return;

    document.querySelectorAll("[data-nt-open]").forEach(function (b) {
      b.addEventListener("click", function () {
        overlay.hidden = false;
        if (API && loadFailed) {
          // Erst-Ladung war fehlgeschlagen → erneut versuchen
          load(function (data) {
            if (loadFailed) return;
            notes = data;
            activeId = notes.length ? notes[0].id : null;
            render();
          });
        }
      });
    });
    document.querySelectorAll("[data-nt-close]").forEach(function (b) {
      b.addEventListener("click", function () { overlay.hidden = true; });
    });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.hidden = true; });
    window.addEventListener("keydown", function (e) { if (e.key === "Escape") overlay.hidden = true; });

    $("nt-new").addEventListener("click", function () {
      var n = { id: uid("n"), title: "", content: "", todos: [], updatedAt: Date.now() };
      notes.unshift(n); activeId = n.id; persist(); render();
      $("nt-ed-title").focus();
    });
    $("nt-delete").addEventListener("click", function () {
      notes = notes.filter(function (n) { return n.id !== activeId; });
      activeId = notes.length ? notes[0].id : null;
      persist(); render();
    });
    $("nt-ed-title").addEventListener("input", function () {
      var n = active(); if (!n) return;
      n.title = this.value; touch(n); renderList();
      $("nt-ed-date").textContent = "Zuletzt bearbeitet: " + fmtDate(n.updatedAt);
    });
    $("nt-ed-content").addEventListener("input", function () {
      var n = active(); if (!n) return;
      n.content = this.value; touch(n); renderList();
    });
    function addTodo() {
      var n = active(); var input = $("nt-todo-input");
      var text = input.value.trim();
      if (!n || !text) return;
      n.todos.push({ id: uid("t"), text: text, done: false });
      input.value = ""; touch(n); render(); input.focus();
    }
    $("nt-todo-add").addEventListener("click", addTodo);
    $("nt-todo-input").addEventListener("keydown", function (e) { if (e.key === "Enter") addTodo(); });

    // Ausstehende (debounced) Speicherung beim Verlassen der Seite flushen
    window.addEventListener("pagehide", function () {
      if (API && dirty && !loadFailed) {
        clearTimeout(saveTimer);
        doSave(true); // keepalive: Request überlebt den Seitenwechsel
      }
    });

    // Uhr in der Statusleiste
    function tick() {
      $("nt-clock").textContent = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    }
    tick(); setInterval(tick, 30000);

    load(function (data) {
      notes = data;
      activeId = notes.length ? notes[0].id : null;
      render();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
