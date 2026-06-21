// Client-side rendering, date-range filtering, and pagination for index.html.
// All events are embedded server-side as JSON (#events-data) — nothing is
// fetched, so this also works when the file is opened directly (file://).
(function () {
  "use strict";

  var PAGE_SIZE = 20;

  var dataEl = document.getElementById("events-data");
  var allEvents = dataEl ? JSON.parse(dataEl.textContent) : [];

  var state = { page: 1, from: null, to: null };

  var AVAILABILITY_LABELS = {
    available: "受付中",
    not_yet_open: "受付前",
    closed: "受付終了",
    sold_out: "完売",
  };

  function formatDateTime(iso) {
    if (!iso) return null;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    try {
      return new Intl.DateTimeFormat("ja-JP", {
        timeZone: "Asia/Tokyo",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(d);
    } catch (e) {
      return iso;
    }
  }

  function sessionMatchesRange(session, fromMs, toMs) {
    if (!session.starts_at) return false;
    var t = new Date(session.starts_at).getTime();
    if (isNaN(t)) return false;
    if (fromMs !== null && t < fromMs) return false;
    if (toMs !== null && t > toMs) return false;
    return true;
  }

  function matchesFilter(event) {
    if (state.from === null && state.to === null) return true;
    var fromMs = state.from !== null ? new Date(state.from + "T00:00:00+09:00").getTime() : null;
    var toMs = state.to !== null ? new Date(state.to + "T23:59:59+09:00").getTime() : null;
    if (!event.sessions || event.sessions.length === 0) return false;
    return event.sessions.some(function (s) {
      return sessionMatchesRange(s, fromMs, toMs);
    });
  }

  function el(tag, opts) {
    var node = document.createElement(tag);
    opts = opts || {};
    if (opts.text) node.textContent = opts.text;
    if (opts.className) node.className = opts.className;
    if (opts.attrs) {
      Object.keys(opts.attrs).forEach(function (k) {
        node.setAttribute(k, opts.attrs[k]);
      });
    }
    return node;
  }

  function renderSession(session) {
    var div = el("div", { className: "session" });
    div.appendChild(el("strong", { text: session.location_label || "" }));
    div.appendChild(document.createTextNode(": " + (formatDateTime(session.starts_at) || "日時未定")));
    if (session.venue_name) div.appendChild(document.createTextNode(" @ " + session.venue_name));
    if (session.venue_address) div.appendChild(document.createTextNode(" (" + session.venue_address + ")"));
    return div;
  }

  function renderReservation(reservation) {
    var div = el("div", { className: "reservation" });
    var label = AVAILABILITY_LABELS[reservation.availability_status];
    if (label) {
      var strong = el("strong", { text: label });
      div.appendChild(strong);
      div.appendChild(el("br"));
    }
    if (reservation.presale_opens_at) {
      div.appendChild(document.createTextNode("予約開始: " + formatDateTime(reservation.presale_opens_at)));
      div.appendChild(el("br"));
    }
    if (reservation.presale_closes_at) {
      div.appendChild(document.createTextNode("予約終了: " + formatDateTime(reservation.presale_closes_at)));
      div.appendChild(el("br"));
    }
    if (reservation.ticket_url) {
      var a = el("a", { text: "予約サイトへ", attrs: { href: reservation.ticket_url } });
      div.appendChild(a);
    }
    return div;
  }

  function renderEvent(event) {
    var card = el("div", { className: "event" });
    var h2 = el("h2");
    h2.appendChild(el("a", { text: event.title, attrs: { href: event.source_url } }));
    card.appendChild(h2);
    (event.sessions || []).forEach(function (session) {
      card.appendChild(renderSession(session));
    });
    card.appendChild(renderReservation(event.reservation || {}));
    return card;
  }

  function renderPagination(totalPages) {
    var container = document.getElementById("pagination");
    container.innerHTML = "";
    if (totalPages <= 1) return;

    function pageButton(label, page, opts) {
      opts = opts || {};
      var btn = el("button", { text: label, attrs: { type: "button" } });
      if (opts.disabled) btn.disabled = true;
      btn.addEventListener("click", function () {
        state.page = page;
        render();
      });
      return btn;
    }

    container.appendChild(pageButton("« 前へ", state.page - 1, { disabled: state.page <= 1 }));
    for (var p = 1; p <= totalPages; p++) {
      container.appendChild(pageButton(String(p), p, { disabled: p === state.page }));
    }
    container.appendChild(pageButton("次へ »", state.page + 1, { disabled: state.page >= totalPages }));
  }

  function render() {
    var filtered = allEvents.filter(matchesFilter);
    var totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (state.page > totalPages) state.page = totalPages;
    if (state.page < 1) state.page = 1;

    var listEl = document.getElementById("events-list");
    listEl.innerHTML = "";

    if (filtered.length === 0) {
      listEl.appendChild(el("p", { text: "該当するイベントはありません。" }));
    } else {
      var start = (state.page - 1) * PAGE_SIZE;
      filtered.slice(start, start + PAGE_SIZE).forEach(function (event) {
        listEl.appendChild(renderEvent(event));
      });
    }

    renderPagination(totalPages);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var fromInput = document.getElementById("filter-from");
    var toInput = document.getElementById("filter-to");

    document.getElementById("filter-apply").addEventListener("click", function () {
      state.from = fromInput.value || null;
      state.to = toInput.value || null;
      state.page = 1;
      render();
    });

    document.getElementById("filter-clear").addEventListener("click", function () {
      fromInput.value = "";
      toInput.value = "";
      state.from = null;
      state.to = null;
      state.page = 1;
      render();
    });

    render();
  });
})();
