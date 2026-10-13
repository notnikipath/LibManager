import React, { useEffect, useState } from "react";

import { KpiCard } from "../components/KpiCard";

const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8600";

const emptyDashboard = {
  patron: { patron_id: "PAT-001", full_name: "" },
  debts: { total_debt_rub: 0, overdue_loans: 0 },
  active_loans: { items: [] },
  reservations: { items: [] },
  recommendations: { material_ids: [] },
  demand: { items: [] },
  kpi: { items: [] },
};

async function fetchDashboard(patronId) {
  const response = await fetch(`${gatewayUrl}/dashboard/patron/${patronId}`);
  if (!response.ok) {
    throw new Error(`Failed to load dashboard: ${response.status}`);
  }
  return response.json();
}

async function searchByTitle(title) {
  const url = new URL(`${gatewayUrl}/catalog/search`, window.location.origin);
  if (title) {
    url.searchParams.set("title", title);
  }
  url.searchParams.set("only_available", "true");
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json();
}

export function DashboardPage() {
  const [patronId, setPatronId] = useState("PAT-001");
  const [search, setSearch] = useState("");
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [searchResult, setSearchResult] = useState({ items: [], count: 0, metrics: null });
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    fetchDashboard(patronId)
      .then((data) => {
        if (!active) return;
        setDashboard({ ...emptyDashboard, ...data });
        setStatus("ok");
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [patronId]);

  const doSearch = async () => {
    try {
      const data = await searchByTitle(search);
      setSearchResult(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const metrics = dashboard.kpi?.items || [];
  const searchMetric = metrics.find((m) => m.metric === "search_time");
  const checkoutMetric = metrics.find((m) => m.metric === "checkout_time");
  const capacityMetric = metrics.find((m) => m.metric === "catalog_capacity");

  return (
    <div className="app">
      <div className="bg-shape bg-left" />
      <div className="bg-shape bg-right" />

      <header className="hero">
        <div>
          <p className="eyebrow">LibManager</p>
          <h1>Library workspace</h1>
          <p className="sub">
            Catalog, patrons, circulation, reservations, digital books, and reporting in one flow.
          </p>
        </div>
        <div className="controls">
          <label>
            Patron ID
            <input value={patronId} onChange={(event) => setPatronId(event.target.value)} />
          </label>
          <label>
            Search title
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Clean Architecture" />
          </label>
          <button onClick={doSearch}>Search in catalog</button>
          <p className="status">Status: {status}</p>
        </div>
      </header>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}

      <section className="kpi-grid">
        <KpiCard
          title="Search Time"
          value={`${Number(searchMetric?.value || 0).toFixed(3)} s`}
          target={`target < ${searchMetric?.target || 1} s`}
          ok={Number(searchMetric?.value || 0) <= Number(searchMetric?.target || 1)}
        />
        <KpiCard
          title="Checkout Time"
          value={`${Number(checkoutMetric?.value || 0).toFixed(3)} s`}
          target={`target < ${checkoutMetric?.target || 10} s`}
          ok={Number(checkoutMetric?.value || 0) <= Number(checkoutMetric?.target || 10)}
        />
        <KpiCard
          title="Catalog Capacity"
          value={Number(capacityMetric?.target || 1000000).toLocaleString()}
          target="titles supported"
          ok
        />
      </section>

      <section className="grid">
        <article className="panel">
          <h2>Patron Profile</h2>
          <p>{dashboard.patron?.full_name || "Unknown patron"}</p>
          <p className="muted">Card: {dashboard.patron?.e_card_number || "-"}</p>
          <p className="muted">Debt: {dashboard.debts?.total_debt_rub || 0} RUB</p>
        </article>

        <article className="panel">
          <h2>Active Loans</h2>
          <div className="stack">
            {(dashboard.active_loans?.items || []).slice(0, 5).map((loan) => (
              <div key={loan.loan_id} className="item-row">
                <span>{loan.material_id}</span>
                <strong>{new Date(loan.due_date).toLocaleDateString()}</strong>
              </div>
            ))}
            {!dashboard.active_loans?.items?.length ? <div className="empty">No active loans</div> : null}
          </div>
        </article>

        <article className="panel">
          <h2>Reservations</h2>
          <div className="stack">
            {(dashboard.reservations?.items || []).slice(0, 5).map((item) => (
              <div key={item.reservation_id} className="item-row">
                <span>{item.material_id}</span>
                <strong>{item.status}</strong>
              </div>
            ))}
            {!dashboard.reservations?.items?.length ? <div className="empty">No reservations</div> : null}
          </div>
        </article>

        <article className="panel panel-wide">
          <h2>Catalog Search Result</h2>
          <p className="muted">Found: {searchResult.count || 0}</p>
          <div className="stack">
            {(searchResult.items || []).slice(0, 8).map((item) => (
              <div key={item.material_id} className="item-row">
                <div>
                  <p>{item.title}</p>
                  <p className="muted">{item.material_type} | available: {item.copies_available}</p>
                </div>
                <strong>{item.classification?.udc}</strong>
              </div>
            ))}
            {!searchResult.items?.length ? <div className="empty">Run search to see matches</div> : null}
          </div>
        </article>

        <article className="panel panel-wide">
          <h2>Recommendations and Demand</h2>
          <p className="muted">Recommended IDs: {(dashboard.recommendations?.material_ids || []).join(", ") || "none"}</p>
          <div className="stack">
            {(dashboard.demand?.items || []).slice(0, 6).map((row) => (
              <div key={row.material_id} className="item-row">
                <span>{row.material_id}</span>
                <strong>score {row.score}</strong>
              </div>
            ))}
            {!dashboard.demand?.items?.length ? <div className="empty">No demand data yet</div> : null}
          </div>
        </article>
      </section>
    </div>
  );
}
