import { useEffect, useMemo, useState } from "react";

import { getLiveLogs, getLogs, type LiveLogsResponse, type LogRow, type LogsResponse } from "../lib/api";

type LogsState = {
  logs: LogsResponse | null;
  live: LiveLogsResponse | null;
  loading: boolean;
  error: string | null;
};

function formatDateTime(value: string | null) {
  if (!value) {
    return "n/a";
  }
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function LogsPage() {
  const [level, setLevel] = useState("all");
  const [source, setSource] = useState("all");
  const [timeWindow, setTimeWindow] = useState("24h");
  const [state, setState] = useState<LogsState>({ logs: null, live: null, loading: true, error: null });

  const load = async (nextLevel = level, nextSource = source, nextTime = timeWindow) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const [logs, live] = await Promise.all([
        getLogs({ level: nextLevel, source: nextSource, time: nextTime }),
        getLiveLogs(),
      ]);
      setState({ logs, live, loading: false, error: null });
    } catch (error) {
      setState({
        logs: null,
        live: null,
        loading: false,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  };

  useEffect(() => {
    void load(level, source, timeWindow);
  }, [level, source, timeWindow]);

  const rows = useMemo(() => state.logs?.rows ?? [], [state.logs]);
  const availableSources = useMemo(() => {
    const found = new Set<string>();
    rows.forEach((row) => found.add(row.source));
    return ["all", ...Array.from(found).sort()];
  }, [rows]);

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Operational logs</p>
          <h3>Logs</h3>
          <p className="panel-message">Inspect API traffic, app events, and a live monospace tail without leaving the dashboard shell.</p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Level</span>
              <select value={level} onChange={(event) => setLevel(event.target.value)}>
                <option value="all">All</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Source</span>
              <select value={source} onChange={(event) => setSource(event.target.value)}>
                {availableSources.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field">
              <span>Time</span>
              <select value={timeWindow} onChange={(event) => setTimeWindow(event.target.value)}>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="24h">24h</option>
                <option value="7d">7d</option>
                <option value="all">All</option>
              </select>
            </label>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void load()}>
              Refresh
            </button>
          </div>
        </div>

        <div className="stats-grid stats-grid-trades">
          <article className="stat-card">
            <p className="metric-label">API rows</p>
            <strong className="metric-value">{state.logs?.summary.api_count ?? 0}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">App rows</p>
            <strong className="metric-value">{state.logs?.summary.app_count ?? 0}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Visible rows</p>
            <strong className="metric-value">{state.logs?.summary.total_count ?? 0}</strong>
          </article>
        </div>

        {state.error ? <p className="panel-message panel-error">Logs unavailable: {state.error}</p> : null}
        {state.loading ? <p className="panel-message">Loading logs...</p> : null}

        <div className="logs-layout">
          <div className="table-wrap">
            <table className="data-table data-table-orders">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Level</th>
                  <th>Kind</th>
                  <th>Source</th>
                  <th>Message</th>
                  <th>Path/Event</th>
                </tr>
              </thead>
              <tbody>
                {!state.loading && !rows.length ? (
                  <tr>
                    <td colSpan={6}>No logs returned for this filter.</td>
                  </tr>
                ) : null}
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateTime(row.created_at)}</td>
                    <td>{row.level}</td>
                    <td>{row.kind}</td>
                    <td>{row.source}</td>
                    <td>{row.message}</td>
                    <td>{formatPathEvent(row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="logs-live-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">Live logs</p>
                <h3>Monospace tail</h3>
              </div>
              <span className="section-pill">{state.live?.lines.length ?? 0} lines</span>
            </div>
            <pre className="monospace-viewer">{(state.live?.lines ?? ["Awaiting log rows..."]).join("\n")}</pre>
          </div>
        </div>
      </article>
    </section>
  );
}

function formatPathEvent(row: LogRow) {
  if (row.kind === "api") {
    return [row.method, row.path, row.status_code].filter(Boolean).join(" · ");
  }
  return row.event_type;
}
