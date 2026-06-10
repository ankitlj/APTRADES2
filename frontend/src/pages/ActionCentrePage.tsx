import { Fragment, useEffect, useMemo, useState } from "react";

import {
  approveAction,
  getActionCentre,
  rejectAction,
  type ActionCentreRecord,
  type ActionCentreResponse,
} from "../lib/api";

type ActionCentreState = {
  data: ActionCentreResponse | null;
  loading: boolean;
  error: string | null;
  message: string | null;
};

const tabs = ["pending", "approved", "rejected", "all"] as const;

function formatDateTime(value: string | null) {
  if (!value) {
    return "n/a";
  }
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ActionCentrePage() {
  const [statusFilter, setStatusFilter] = useState<(typeof tabs)[number]>("pending");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [state, setState] = useState<ActionCentreState>({ data: null, loading: true, error: null, message: null });

  const load = async (nextStatus = statusFilter) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await getActionCentre(nextStatus);
      setState((current) => ({ ...current, data, loading: false, error: null }));
    } catch (error) {
      setState((current) => ({
        ...current,
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void load(statusFilter);
  }, [statusFilter]);

  const actions = useMemo(() => state.data?.actions ?? [], [state.data]);

  const mutate = async (row: ActionCentreRecord, operation: "approve" | "reject") => {
    try {
      const response = operation === "approve" ? await approveAction(row.id) : await rejectAction(row.id);
      setState((current) => ({
        ...current,
        message: `${operation === "approve" ? "Approved" : "Rejected"} order ${response.action.order_id}.`,
      }));
      await load(statusFilter);
    } catch (error) {
      setState((current) => ({
        ...current,
        message: error instanceof Error ? error.message : `Unable to ${operation} this action.`,
      }));
    }
  };

  const stats = state.data?.stats ?? { pending: 0, approved: 0, rejected: 0, all: 0 };

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Broker actions</p>
          <h3>Action Centre</h3>
          <p className="panel-message">Review queued broker actions, approve live requests, or reject them with full audit rows.</p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="info-banner">
          <strong>Semi-auto workflow</strong>
          <span>Pending rows are sourced from live broker orders. Approve sends the linked Breeze action. Reject keeps the audit trail without touching the broker.</span>
        </div>

        <div className="route-toolbar">
          <div className="tab-strip">
            {tabs.map((tab) => (
              <button
                key={tab}
                type="button"
                className={tab === statusFilter ? "tab-chip tab-chip-active" : "tab-chip"}
                onClick={() => setStatusFilter(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void load()}>
              Refresh
            </button>
          </div>
        </div>

        <div className="stats-grid stats-grid-orders">
          <article className="stat-card">
            <p className="metric-label">Pending</p>
            <strong className="metric-value">{stats.pending}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Approved</p>
            <strong className="metric-value">{stats.approved}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Rejected</p>
            <strong className="metric-value">{stats.rejected}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">All</p>
            <strong className="metric-value">{stats.all}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Current tab</p>
            <strong className="metric-value">{statusFilter}</strong>
          </article>
        </div>

        {state.message ? <p className="panel-message">{state.message}</p> : null}
        {state.error ? <p className="panel-message panel-error">Action Centre unavailable: {state.error}</p> : null}
        {state.loading ? <p className="panel-message">Loading action queue...</p> : null}
        {!state.loading && !state.error && !actions.length ? <p className="panel-message">No rows returned for this status.</p> : null}

        {!state.loading && !state.error && actions.length ? (
          <div className="table-wrap">
            <table className="data-table data-table-orders">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Action</th>
                  <th>Order ID</th>
                  <th className="numeric">Qty</th>
                  <th>Requested</th>
                  <th>Reviewed</th>
                  <th>Controls</th>
                </tr>
              </thead>
              <tbody>
                {actions.map((row) => (
                  <Fragment key={row.id}>
                    <tr key={row.id}>
                      <td>
                        <div className="table-symbol">
                          <strong>{row.symbol}</strong>
                          <span>{row.exchange_code} · {row.product_type ?? "n/a"}</span>
                        </div>
                      </td>
                      <td>{row.status}</td>
                      <td>{row.action_type}</td>
                      <td>{row.order_id}</td>
                      <td className="numeric">{row.quantity ?? "n/a"}</td>
                      <td>{formatDateTime(row.requested_at)}</td>
                      <td>{formatDateTime(row.reviewed_at)}</td>
                      <td>
                        <div className="row-actions-inline">
                          <button
                            type="button"
                            className="row-action"
                            onClick={() => void mutate(row, "approve")}
                            disabled={!row.can_approve}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            className="row-action"
                            onClick={() => void mutate(row, "reject")}
                            disabled={!row.can_reject}
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            className="row-action"
                            onClick={() => setExpandedId((current) => (current === row.id ? null : row.id))}
                          >
                            {expandedId === row.id ? "Hide" : "Details"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === row.id ? (
                      <tr className="expanded-row">
                        <td colSpan={8}>
                          <div className="expanded-panel">
                            <div className="expanded-meta-grid">
                              <div>
                                <p className="metric-label">Requested by</p>
                                <strong>{row.requested_by}</strong>
                              </div>
                              <div>
                                <p className="metric-label">Created from</p>
                                <strong>{row.created_from}</strong>
                              </div>
                              <div>
                                <p className="metric-label">Note</p>
                                <strong>{row.resolution_note ?? "Awaiting review"}</strong>
                              </div>
                            </div>
                            <div className="logs-live-panel">
                              <p className="metric-label">Request payload</p>
                              <pre className="monospace-viewer">{JSON.stringify(row.request_payload ?? {}, null, 2)}</pre>
                            </div>
                            <div className="logs-live-panel">
                              <p className="metric-label">Broker result</p>
                              <pre className="monospace-viewer">{JSON.stringify(row.broker_result ?? {}, null, 2)}</pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
