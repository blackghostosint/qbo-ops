(function () {
  "use strict";
  // qbo-ops web dashboard page: QuickBooks connection health + month summary.
  // Boring-and-true: data display only, SDK components only, no cleverness.
  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  var React = SDK.React;
  var hooks = SDK.hooks;
  var C = SDK.components || {};
  var fetchJSON = SDK.authedFetch || SDK.fetchJSON || function (url, opts) {
    return fetch(url, opts).then(function (r) { return r.json(); });
  };

  var API = "/api/plugins/qbo-ops";

  function usePluginData(path, intervalMs) {
    var state = hooks.useState({ loading: true, data: null, error: null });
    var set = state[1];
    hooks.useEffect(function () {
      var alive = true;
      function load() {
        fetchJSON(API + path).then(function (d) {
          if (alive) set({ loading: false, data: d, error: null });
        }).catch(function (e) {
          if (alive) set({ loading: false, data: null, error: String(e && e.message || e) });
        });
      }
      load();
      var t = setInterval(load, intervalMs || 60000);
      return function () { alive = false; clearInterval(t); };
    }, [path]);
    return state[0];
  }

  function StatusDot(props) {
    var color = props.status === "connected" ? "#5ec26a"
      : props.status === "reauth_required" ? "#e0a83c"
      : props.status === "unconfigured" ? "#8b97b8"
      : "#d4626a";
    return React.createElement("span", {
      style: { display: "inline-block", width: "10px", height: "10px",
               borderRadius: "50%", background: color, marginRight: "8px" }
    });
  }

  function Card2(props) {
    if (C.Card) {
      return React.createElement(C.Card, { style: props.style },
        React.createElement(C.CardHeader, null,
          React.createElement(C.CardTitle, null, props.title)),
        React.createElement(C.CardContent, null, props.children));
    }
    // fallback for older hosts without the component set
    return React.createElement("div", {
      style: Object.assign({ border: "1px solid rgba(128,140,170,.35)",
        borderRadius: "12px", padding: "16px 20px", margin: "12px 0" }, props.style) },
      React.createElement("div", { style: { fontWeight: 600, marginBottom: "8px" } }, props.title),
      props.children);
  }

  function fmt(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function QboPage() {
    var health = usePluginData("/health", 60000);
    var h = health.data || {};
    var connected = h.status === "connected";

    var pnl = usePluginData("/pnl", 120000);
    var p = pnl.data || {};

    var audit = usePluginData("/audit", 120000);
    var a = audit.data || {};

    var today = new Date();
    var monthName = today.toLocaleString("en-US", { month: "long" });

    return React.createElement("div", { style: { padding: "20px 24px", maxWidth: "860px" } },
      React.createElement("h2", { style: { margin: "0 0 4px", fontSize: "22px" } }, "QuickBooks Online"),
      React.createElement("div", { style: { opacity: 0.7, fontSize: "13px", marginBottom: "18px" } },
        "qbo-ops · agent tools: qbo_health, qbo_pnl, qbo_udf_audit, qbo_deposit_trace, qbo_query"),

      React.createElement(Card2, { title: "Connection" },
        health.loading
          ? React.createElement("span", null, "Checking…")
          : React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "6px", fontSize: "15px" } },
              React.createElement(StatusDot, { status: h.status }),
              React.createElement("span", null,
                connected ? (h.company || "Connected") : (h.message || h.status))),

        connected && React.createElement("div", { style: { opacity: 0.6, fontSize: "12px", marginTop: "8px" } },
          "realm " + (h.realm_id || "?") + " · transport " + (h.transport || "?"))),

      connected && React.createElement(Card2, { title: "This month (" + monthName + ")" },
        pnl.loading
          ? React.createElement("span", null, "Loading…")
          : React.createElement("div", { style: { display: "flex", gap: "36px", fontSize: "18px" } },
              React.createElement("div", null,
                React.createElement("div", { style: { opacity: 0.6, fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px" } }, "Income"),
                React.createElement("div", null, fmt(p.income))),
              React.createElement("div", null,
                React.createElement("div", { style: { opacity: 0.6, fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px" } }, "Expenses"),
                React.createElement("div", null, fmt(p.expenses))),
              React.createElement("div", null,
                React.createElement("div", { style: { opacity: 0.6, fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px" } }, "Net"),
                React.createElement("div", { style: { fontWeight: 700 } }, fmt(p.net_income))))),

      connected && React.createElement(Card2, { title: "Close audit (last 24h)" },
        audit.loading
          ? React.createElement("span", null, "Loading…")
          : React.createElement("div", { fontSize: "15px" },
              (a.flag_count === 0
                ? "Clean — no backdated entries flagged."
                : a.flag_count + " entr" + (a.flag_count === 1 ? "y" : "ies") + " flagged for review.")),

        connected && React.createElement("div", { style: { opacity: 0.55, fontSize: "12px", marginTop: "16px" } },
          "Ask your agent for the interactive versions: \"how did last month look?\" · \"trace this deposit\" · \"run a close audit since Friday\""))
    );
  }

  window.__HERMES_PLUGINS__.register("qbo-ops", QboPage);
})();
