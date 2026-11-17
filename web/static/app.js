const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const state = { live: null, results: null, curve: "oos_05", view: "overview" };

const numberFmt = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const intFmt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(value, signed = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const body = numberFmt.format(Math.abs(n)) + " $";
  if (n < 0) return "-" + body;
  if (signed && n > 0) return "+" + body;
  return body;
}

function pct(value, signed = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const body = n.toFixed(2).replace(".", ",") + " %";
  if (signed && n > 0) return "+" + body;
  return body;
}

function rfmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  return (n > 0 ? "+" : "") + n.toFixed(3).replace(".", ",") + " R";
}

function riskfmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(1).replace(".", ",") + " %";
}

function compactMoney(value) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(2).replace(".", ",") + " M$";
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1).replace(".", ",") + " k$";
  return n.toFixed(0) + " $";
}

function timeShort(iso) {
  if (!iso) return "—";
  const text = String(iso);
  if (text.length >= 16 && text[10] === "T") return text.slice(11, 16);
  return text;
}

function dateShort(value) {
  if (!value) return "—";
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
    return text.slice(8, 10) + "/" + text.slice(5, 7) + "/" + text.slice(2, 4);
  }
  return text;
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value ?? "—";
}

function markPnl(node) {
  const value = Number(node?.dataset.value ?? 0);
  node?.classList.remove("good", "bad");
  if (value > 0) node?.classList.add("good");
  if (value < 0) node?.classList.add("bad");
}

function showError(message) {
  const banner = $("error-banner");
  banner.textContent = message;
  banner.classList.remove("hidden");
}

function hideError() {
  $("error-banner").classList.add("hidden");
}

async function fetchJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === "view-" + view);
  });
  history.replaceState(null, "", view === "overview" ? "/" : "#" + view);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "overview" && state.results) drawChart(state.curve);
}

function marketClass(status) {
  if (status === "open" || status === "range") return "open";
  if (status === "weekend" || status === "closed") return "closed";
  return "";
}

function executionNote(phase) {
  const notes = {
    weekend: "Marché fermé ce week-end. Le bot reprendra lundi à 09:30 NY.",
    pre_range: "En attente du range 09:30-09:45 NY. Aucune entrée avant validation.",
    opening_range: "Range en formation. L'EA attend 09:45 pour évaluer les filtres.",
    entry_window: "Fenêtre d'entrée active. Le bot attend une cassure validée par les filtres.",
    after_close: "Clôture de sécurité passée. Aucune nouvelle entrée aujourd'hui.",
  };
  return notes[phase] || "Lecture de la session en cours.";
}

function timelineFor(phase) {
  if (phase === "weekend") return {};
  if (phase === "pre_range") return { pre: "current" };
  if (phase === "opening_range") return { pre: "done", range: "current" };
  if (phase === "entry_window") return { pre: "done", range: "done", entry: "current" };
  return { pre: "done", range: "done", entry: "done" };
}

function renderTimeline(phase) {
  const active = timelineFor(phase);
  document.querySelectorAll(".timeline-step").forEach((step) => {
    const name = step.dataset.step;
    step.classList.toggle("done", active[name] === "done");
    step.classList.toggle("current", active[name] === "current");
  });
}

function renderPositions(positions) {
  const body = $("positions-body");
  if (!positions.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">Aucune position ouverte.</td></tr>';
    return;
  }
  body.innerHTML = positions
    .map((position) => {
      const pnl = Number(position.profit ?? 0) + Number(position.swap ?? 0);
      return `<tr>
        <td><span class="symbol-cell"><span class="symbol-dot ${position.is_orb ? "orb" : ""}"></span>${esc(position.symbol)}</span></td>
        <td class="${position.side === "BUY" ? "side-buy" : "side-sell"}">${esc(position.side)}</td>
        <td class="num">${esc(position.volume)}</td>
        <td class="num">${esc(position.price_open)}</td>
        <td class="num ${pnl >= 0 ? "good" : "bad"}">${money(pnl, true)}</td>
      </tr>`;
    })
    .join("");
}

function renderDeals(target, deals, timeKey = "time_ny") {
  const body = $(target);
  if (!deals.length) {
    const columns = target === "deals-body" ? 4 : 6;
    body.innerHTML = `<tr><td colspan="${columns}" class="empty">Aucun deal aujourd'hui.</td></tr>`;
    return;
  }
  body.innerHTML = deals
    .map((deal) => {
      const profit = Number(deal.profit ?? 0) + Number(deal.swap ?? 0) + Number(deal.commission ?? 0);
      if (target === "deals-body") {
        return `<tr>
          <td class="num">${esc(timeShort(deal[timeKey]))}</td>
          <td>${esc(deal.entry_label ?? "")}</td>
          <td>${esc(deal.symbol)}</td>
          <td class="num ${profit >= 0 ? "good" : "bad"}">${money(profit, true)}</td>
        </tr>`;
      }
      return `<tr>
        <td class="num">${esc(timeShort(deal[timeKey]))}</td>
        <td>${esc(deal.symbol)}</td>
        <td class="${deal.side === "BUY" ? "side-buy" : "side-sell"}">${esc(deal.side)}</td>
        <td class="num">${esc(deal.volume)}</td>
        <td class="num">${esc(deal.price)}</td>
        <td class="num ${profit >= 0 ? "good" : "bad"}">${money(profit, true)}</td>
      </tr>`;
    })
    .join("");
}

function renderOrders(orders) {
  const body = $("orders-body");
  setText("orders-count", orders.length);
  if (!orders.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">Aucun ordre en attente.</td></tr>';
    return;
  }
  body.innerHTML = orders
    .map(
      (order) => `<tr>
        <td>${esc(order.symbol)}</td>
        <td class="${order.side === "BUY" ? "side-buy" : "side-sell"}">${esc(order.side)}</td>
        <td class="num">${esc(order.volume_current ?? order.volume_initial ?? "")}</td>
        <td class="num">${esc(order.price_open ?? "")}</td>
        <td class="num">${esc(order.magic)}</td>
        <td class="muted">${esc(order.comment ?? "")}</td>
      </tr>`
    )
    .join("");
}

function renderLogs(logs) {
  const list = $("log-list");
  list.innerHTML = "";
  setText("log-count", logs.length);
  if (!logs.length) {
    list.innerHTML = '<div class="log-empty">Aucun log disponible.</div>';
    return;
  }
  logs.forEach((item) => {
    const line = document.createElement("div");
    const hot = /ORB|range|entry|close|trade|error|failed|market closed/i.test(item.line);
    line.className = "log-line" + (hot ? " hot" : "");
    const source = document.createElement("span");
    source.className = "log-source";
    source.textContent = item.source;
    const text = document.createElement("span");
    text.textContent = item.line;
    line.append(source, text);
    list.appendChild(line);
  });
  list.scrollTop = list.scrollHeight;
}

function renderConfig(config) {
  const body = $("config-body");
  const entries = Object.entries(config || {});
  setText("config-count", entries.length + " inputs");
  if (!entries.length) {
    body.innerHTML = '<tr><td colspan="2" class="empty">Configuration indisponible.</td></tr>';
    return;
  }
  body.innerHTML = entries
    .map(
      ([key, value]) =>
        `<tr><td>${esc(key)}</td><td>${esc(typeof value === "boolean" ? (value ? "true" : "false") : value)}</td></tr>`
    )
    .join("");
}

function renderLive(data) {
  state.live = data;
  const market = data.market || {};
  const config = data.config || {};
  const account = data.account || {};
  const symbol = data.symbol || {};
  const server = data.server || {};
  const today = data.today || {};

  setText("clock", market.ny_clock ?? "--:--:--");
  setText("market-label", data.ok ? market.label : "MT5 indisponible");
  const pill = $("market-pill");
  pill.classList.remove("open", "closed");
  pill.classList.add(data.ok ? marketClass(market.status) : "closed");
  const pillDot = pill.querySelector(".status-dot");
  pillDot.className = "status-dot " + (data.ok ? (marketClass(market.status) === "open" ? "online" : "warn") : "offline");

  const sideDot = $("side-dot");
  sideDot.className = "status-dot " + (data.ok ? "online" : "offline");
  setText("side-status", data.ok ? "MT5 connecté" : "MT5 indisponible");
  setText("side-detail", data.ok ? `${account.server ?? ""} · ${account.login ?? ""}` : data.error || "Terminal fermé.");
  setText("side-login", account.login ?? "—");
  setText("side-risk", config.InpRiskPct !== undefined ? riskfmt(config.InpRiskPct) : "—");

  setText("equity", money(account.equity));
  setText("balance", money(account.balance));
  const dayPnl = Number(today.realized ?? 0);
  const dayNode = $("day-pnl");
  dayNode.textContent = money(dayPnl, true);
  dayNode.dataset.value = dayPnl;
  markPnl(dayNode);
  const openPnl = Number(account.profit ?? 0);
  const openNode = $("open-pnl");
  openNode.textContent = money(openPnl, true);
  openNode.dataset.value = openPnl;
  markPnl(openNode);
  setText("free-margin", money(account.margin_free));
  setText("account-server", account.server ?? "MT5");
  setText("last-update", data.generated_at ? timeShort(data.generated_at) : "—");
  setText("hero-status", data.ok ? `${market.label} · ${market.ny_date ?? ""}` : "Terminal hors ligne");
  setText("hero-next", market.next_event ? "Prochain jalon : " + market.next_event : "—");

  const positions = data.positions || [];
  const orbPositions = positions.filter((item) => item.is_orb);
  setText("positions-count", positions.length);
  setText("positions-sub", orbPositions.length + " ORB · " + (positions.length - orbPositions.length) + " hors ORB");
  setText("positions-tag", positions.length);
  renderPositions(positions);

  const tradeCount = Number(today.count ?? 0);
  setText("trades-count", tradeCount);
  setText("trades-sub", `${today.wins ?? 0} gagnants · ${today.losses ?? 0} perdants`);
  setText("realized-day", money(dayPnl, true));
  setText("win-loss", `${today.wins ?? 0} / ${today.losses ?? 0}`);
  renderDeals("deals-body", today.deals || []);

  const riskPct = Number(config.InpRiskPct ?? 0);
  setText("risk-value", config.InpRiskPct !== undefined ? riskfmt(config.InpRiskPct) : "—");
  setText("risk-money", account.equity ? money((Number(account.equity) * riskPct) / 100) : "—");
  setText("phase-label", market.label ?? "—");
  setText("next-event", market.next_event ?? "—");
  setText("spread", symbol.spread !== null && symbol.spread !== undefined ? numberFmt.format(symbol.spread) + " pts" : "—");
  setText("bid-ask", symbol.bid !== null && symbol.bid !== undefined ? `${numberFmt.format(symbol.bid)} / ${numberFmt.format(symbol.ask)}` : "—");
  const ping = server.ping_ms;
  setText("ping", ping === null || ping === undefined ? "—" : Number(ping) > 1000 ? Math.round(Number(ping) / 1000) + " s" : ping + " ms");
  setText("build", server.build ? "build " + server.build : "—");
  setText("execution-note", executionNote(market.phase));
  renderTimeline(market.phase);

  const ea = data.ea || {};
  const eaTag = $("ea-tag");
  eaTag.textContent = ea.loaded ? "EA actif" : "EA non détecté";
  eaTag.className = "tag " + (ea.loaded ? "tag-good" : "tag-bad");

  renderDeals("journal-deals-body", today.deals || []);
  setText("deals-count", (today.deals || []).length);
  setText("journal-realized", money(dayPnl, true));
  setText("journal-win-loss", `${today.wins ?? 0} / ${today.losses ?? 0}`);
  setText("journal-magic", config.InpMagic ?? "20261115");
  renderOrders(data.orders || []);
  renderLogs(data.logs || []);
  renderConfig(config);

  if (data.ok) hideError();
  else showError("MT5 : " + (data.error || "connexion indisponible"));
}

function renderDirect(runs) {
  const body = $("direct-body");
  if (!runs.length) {
    body.innerHTML = '<tr><td colspan="10" class="empty">Aucun résultat direct.</td></tr>';
    return;
  }
  body.innerHTML = runs
    .map((run) => {
      const tagClass =
        run.id === "both_12m_05"
          ? "tag-good"
          : run.tag === "rejeté" || run.tag === "agressif"
            ? "tag-warn"
            : "tag-soft";
      return `<tr class="${run.id === "both_12m_05" ? "focus" : ""}">
        <td>${esc(run.label)}<br><span class="muted">${esc(run.short)}</span></td>
        <td class="muted">${esc(run.period)}</td>
        <td class="num">${riskfmt(run.risk)}</td>
        <td class="num">${esc(run.trades)}</td>
        <td class="num">${pct(run.win_rate)}</td>
        <td class="num">${rfmt(run.avg_r)}</td>
        <td class="num ${run.max_dd > 10 ? "bad" : "good"}">${pct(run.max_dd)}</td>
        <td class="num">${money(run.final)}</td>
        <td class="num ${run.per_day >= 50 ? "good" : ""}">${money(run.per_day)}</td>
        <td><span class="tag ${tagClass}">${esc(run.tag)}</span></td>
      </tr>`;
    })
    .join("");
}

function renderPeriodRows(target, rows) {
  const body = $(target);
  if (!rows || !rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">Aucune donnée.</td></tr>';
    return;
  }
  body.innerHTML = rows
    .map(
      (row) => `<tr class="${row.period === "oos" ? "focus" : ""}">
        <td>${esc(row.label)}</td>
        <td class="num">${esc(row.trades)}</td>
        <td class="num">${rfmt(row.avg_r)}</td>
        <td class="num ${row.return_pct >= 0 ? "good" : "bad"}">${pct(row.return_pct, true)}</td>
        <td class="num ${row.max_dd_pct > 10 ? "bad" : "good"}">${pct(row.max_dd_pct)}</td>
      </tr>`
    )
    .join("");
}

function renderRiskFrontier(rows) {
  const grid = $("risk-grid");
  if (!rows.length) {
    grid.innerHTML = '<div class="log-empty">Aucune donnée.</div>';
    return;
  }
  grid.innerHTML = rows
    .map((row) => {
      const hot = row.max_dd_pct > 10;
      const width = Math.min(100, (row.max_dd_pct / 35) * 100);
      return `<div class="risk-item ${hot ? "hot" : "good"}">
        <div class="risk-top">
          <span class="risk-risk">${riskfmt(row.risk_pct)}</span>
          <span class="risk-return">${pct(row.return_pct, true)}</span>
        </div>
        <div class="risk-bar"><span style="width:${width}%"></span></div>
        <div class="risk-dd">DD ${pct(row.max_dd_pct)}</div>
        <span class="risk-day">${money(row.per_day)} / jour · ${esc(row.trades)} trades</span>
      </div>`;
    })
    .join("");
}

function renderRecentTrades(trades) {
  const body = $("recent-trades-body");
  setText("recent-count", trades.length + " trades");
  if (!trades.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty">Aucun trade.</td></tr>';
    return;
  }
  body.innerHTML = trades
    .map(
      (trade) => `<tr>
        <td class="num">${esc(dateShort(trade.date))}</td>
        <td class="${trade.side === "LONG" ? "side-buy" : "side-sell"}">${esc(trade.side)}</td>
        <td class="num">${numberFmt.format(trade.entry)}</td>
        <td class="num">${numberFmt.format(trade.exit)}</td>
        <td class="num ${trade.r >= 0 ? "good" : "bad"}">${rfmt(trade.r)}</td>
        <td class="num ${trade.pnl >= 0 ? "good" : "bad"}">${money(trade.pnl, true)}</td>
        <td class="muted">${esc(trade.reason)}</td>
      </tr>`
    )
    .join("");
}

function renderChartTabs(curves) {
  const tabs = $("chart-tabs");
  tabs.innerHTML = Object.entries(curves)
    .map(
      ([key, curve]) =>
        `<button class="chart-tab ${key === state.curve ? "active" : ""}" data-curve="${esc(key)}" type="button">${esc(curve.label)}</button>`
    )
    .join("");
  tabs.querySelectorAll(".chart-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.curve = button.dataset.curve;
      renderChartTabs(state.results.curves);
      drawChart(state.curve);
    });
  });
}

function svgEl(tag, attrs = {}, text = "") {
  const element = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  if (text) element.textContent = text;
  return element;
}

function drawChart(key) {
  const curve = state.results?.curves?.[key];
  if (!curve) return;
  const svg = $("equity-chart");
  const tip = $("chart-tip");
  const points = curve.points || [];
  svg.innerHTML = "";
  tip.classList.add("hidden");
  setText("chart-title", curve.label);
  setText("chart-sub", curve.sub);
  setText("chart-return", pct(curve.return_pct, true));
  setText("chart-dd", pct(curve.max_dd_pct));
  setText("chart-last", points.length ? money(points[points.length - 1].value) : "—");
  if (!points.length) {
    svg.appendChild(svgEl("text", { x: 450, y: 160, "text-anchor": "middle", fill: "#64748b", "font-size": "12" }, "Aucune donnée de courbe"));
    return;
  }

  const W = 900;
  const H = 320;
  const ml = 64;
  const mr = 16;
  const mt = 18;
  const mb = 34;
  const plotW = W - ml - mr;
  const plotH = H - mt - mb;
  const values = points.map((point) => Number(point.value));
  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);
  const pad = Math.max((maxValue - minValue) * 0.09, Math.max(1, maxValue * 0.003));
  minValue -= pad;
  maxValue += pad;

  const defs = svgEl("defs");
  const gradient = svgEl("linearGradient", { id: "area-grad", x1: "0", y1: "0", x2: "0", y2: "1" });
  gradient.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#5eead4", "stop-opacity": "0.24" }));
  gradient.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#5eead4", "stop-opacity": "0" }));
  defs.appendChild(gradient);
  svg.appendChild(defs);

  const xFor = (index) => ml + (index / Math.max(1, points.length - 1)) * plotW;
  const yFor = (value) => mt + ((maxValue - value) / (maxValue - minValue)) * plotH;

  for (let i = 0; i <= 4; i += 1) {
    const ratio = i / 4;
    const y = mt + ratio * plotH;
    svg.appendChild(svgEl("line", { x1: ml, y1: y, x2: W - mr, y2: y, stroke: "rgba(148,163,184,0.09)", "stroke-width": "1" }));
    const value = maxValue - ratio * (maxValue - minValue);
    svg.appendChild(svgEl("text", { x: ml - 8, y: y + 3, "text-anchor": "end", fill: "#64748b", "font-size": "9", "font-family": "Cascadia Code, monospace" }, compactMoney(value)));
  }

  const line = points.map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(point.value).toFixed(2)}`).join(" ");
  const area = `${line} L ${xFor(points.length - 1).toFixed(2)} ${mt + plotH} L ${xFor(0).toFixed(2)} ${mt + plotH} Z`;
  svg.appendChild(svgEl("path", { d: area, fill: "url(#area-grad)" }));
  svg.appendChild(svgEl("path", { d: line, fill: "none", stroke: "#5eead4", "stroke-width": "2", "stroke-linejoin": "round", "stroke-linecap": "round" }));

  const last = points[points.length - 1];
  svg.appendChild(svgEl("circle", { cx: xFor(points.length - 1), cy: yFor(last.value), r: "3.5", fill: "#5eead4", stroke: "#071018", "stroke-width": "2" }));

  const labelCount = Math.min(5, points.length);
  for (let i = 0; i < labelCount; i += 1) {
    const index = Math.round((i / Math.max(1, labelCount - 1)) * (points.length - 1));
    const point = points[index];
    svg.appendChild(
      svgEl(
        "text",
        { x: xFor(index), y: H - 12, "text-anchor": i === 0 ? "start" : i === labelCount - 1 ? "end" : "middle", fill: "#64748b", "font-size": "9", "font-family": "Cascadia Code, monospace" },
        dateShort(point.date)
      )
    );
  }

  const overlay = svgEl("rect", { x: ml, y: mt, width: plotW, height: plotH, fill: "transparent" });
  overlay.addEventListener("mousemove", (event) => {
    const rect = svg.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * W;
    const index = Math.max(0, Math.min(points.length - 1, Math.round(((x - ml) / plotW) * (points.length - 1))));
    const point = points[index];
    tip.innerHTML = `<span>${esc(point.date)}</span><br><strong>${money(point.value)}</strong>`;
    tip.classList.remove("hidden");
    tip.style.left = ((xFor(index) / W) * rect.width) + "px";
    tip.style.top = ((yFor(point.value) / H) * rect.height) + "px";
  });
  overlay.addEventListener("mouseleave", () => tip.classList.add("hidden"));
  svg.appendChild(overlay);
}

function renderResults(data) {
  state.results = data;
  const direct = data.direct || {};
  const oos = data.oos || {};
  const primary = oos.primary || {};
  setText("direct-source", direct.source || "report.md");
  renderDirect(direct.runs || []);
  renderPeriodRows("oos-body", oos.rows || []);
  renderPeriodRows("stress-body", oos.stress || []);
  renderRiskFrontier(oos.risk_frontier || []);
  renderRecentTrades(data.recent_trades || []);
  renderChartTabs(data.curves || {});
  drawChart(state.curve);
  setText("oos-dd", pct(primary.max_dd_pct));
  setText("oos-r", rfmt(primary.avg_r));
  setText("oos-trades", (primary.trades || 0) + " trades OOS");
  setText("oos-note", data.notes?.[0] || "");
  setText("calibration-text", data.calibration?.text || "");
}

async function refreshLive(manual = false) {
  const live = await fetchJSON("/api/live");
  renderLive(live);
  if (manual) hideError();
}

async function refreshAll(manual = false) {
  const button = $("refresh");
  button.classList.add("loading");
  button.disabled = true;
  const [liveResult, resultsResult] = await Promise.allSettled([
    fetchJSON("/api/live"),
    fetchJSON("/api/results"),
  ]);
  if (liveResult.status === "fulfilled") renderLive(liveResult.value);
  if (resultsResult.status === "fulfilled") renderResults(resultsResult.value);
  if (liveResult.status === "rejected" && resultsResult.status === "rejected") {
    showError("Impossible de charger le dashboard. Vérifiez que le serveur Flask tourne.");
  } else if (liveResult.status === "rejected") {
    showError("MT5 : " + liveResult.reason.message);
  } else if (manual) {
    hideError();
  }
  button.classList.remove("loading");
  button.disabled = false;
}

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

$("refresh").addEventListener("click", () => refreshAll(true));

const initialView = window.location.hash.replace("#", "");
if (["overview", "results", "analysis", "journal", "config"].includes(initialView)) {
  switchView(initialView);
}

refreshAll();
setInterval(() => {
  refreshLive().catch(() => {});
}, 15000);
