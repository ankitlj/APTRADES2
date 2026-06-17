import { AppWindow, List, Server } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getLiveLogs, getLogs, type LiveLogsResponse, type LogRow, type LogsResponse } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTableShell } from "@/components/ui/data-table-shell";
import { PageLayout } from "@/components/ui/page-layout";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";

type LogsState = {
  logs: LogsResponse | null;
  live: LiveLogsResponse | null;
  loading: boolean;
  error: string | null;
};

function formatDateTime(value: string | null) {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value)
  );
}

function formatPathEvent(row: LogRow) {
  if (row.kind === "api") {
    return [row.method, row.path, row.status_code].filter(Boolean).join(" \u00B7 ");
  }
  return row.event_type;
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
    <PageLayout>
      <PageHeader
        kicker="Operational logs"
        title="Logs"
        description="Inspect API traffic, app events, and a live monospace tail without leaving the dashboard shell."
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Field label="Level">
            <select value={level} onChange={(event) => setLevel(event.target.value)} className={selectClass}>
              <option value="all">All</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </Field>
          <Field label="Source">
            <select value={source} onChange={(event) => setSource(event.target.value)} className={selectClass}>
              {availableSources.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Time">
            <select value={timeWindow} onChange={(event) => setTimeWindow(event.target.value)} className={selectClass}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="24h">24h</option>
              <option value="7d">7d</option>
              <option value="all">All</option>
            </select>
          </Field>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="API rows" value={state.logs?.summary.api_count ?? 0} icon={Server} />
        <StatCard label="App rows" value={state.logs?.summary.app_count ?? 0} icon={AppWindow} />
        <StatCard label="Visible rows" value={state.logs?.summary.total_count ?? 0} icon={List} />
      </div>

      {state.error ? <ErrorState title="Logs unavailable" message={state.error} onRetry={() => void load()} /> : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
        <DataTableShell
          title="Log rows"
          count={rows.length}
          loading={state.loading && !rows.length}
          error={state.error}
          onRetry={() => void load()}
          emptyMessage="No logs returned for this filter."
          emptyTitle="No logs"
          minWidth="700px"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Level</th>
                <th className="px-4 py-3 font-medium">Kind</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Message</th>
                <th className="px-4 py-3 font-medium">Path/Event</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-muted/20">
                  <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDateTime(row.created_at)}</td>
                  <td className="px-4 py-3">{row.level}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.kind}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.source}</td>
                  <td className="px-4 py-3">{row.message}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatPathEvent(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </DataTableShell>

        <Card className="overflow-hidden">
          <CardHeader className="flex-row items-center justify-between gap-2 border-b px-4 py-3">
            <CardTitle className="text-sm">Live logs</CardTitle>
            <Badge variant="secondary">{state.live?.lines.length ?? 0} lines</Badge>
          </CardHeader>
          <div className="p-3">
            <pre className="max-h-[420px] overflow-auto rounded-md border bg-muted/50 p-3 text-xs font-mono">
              {(state.live?.lines ?? ["Awaiting log rows..."]).join("\n")}
            </pre>
          </div>
        </Card>
      </div>
    </PageLayout>
  );
}
