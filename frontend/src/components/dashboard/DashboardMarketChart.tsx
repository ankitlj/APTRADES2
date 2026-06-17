import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getDashboardChart, type DashboardChartResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ChartPoint {
  time: string | null;
  value: number;
}

interface Coordinate {
  x: number;
  y: number;
}

const SUGGESTED_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"];

function formatTimeLabel(time: string | null, interval: string): string {
  if (!time) return "";
  try {
    const d = new Date(time);
    if (isNaN(d.getTime())) return "";
    const isIntraday =
      interval.toLowerCase().includes("minute") || interval.toLowerCase().includes("min");
    if (isIntraday) {
      return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
    }
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
  } catch {
    return "";
  }
}

function formatTooltipTime(time: string | null): string {
  if (!time) return "";
  try {
    const d = new Date(time);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "";
  }
}

function buildSvgPath(points: ChartPoint[], width: number, height: number) {
  if (points.length === 0) return { line: "", area: "", coordinates: [] as Coordinate[] };

  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const xStep = points.length > 1 ? width / (points.length - 1) : width;

  const coordinates = points.map((point, index) => {
    const x = index * xStep;
    const y = height - ((point.value - minValue) / range) * (height - 28) - 14;
    return { x, y };
  });

  const line = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${width} ${height} L0 ${height} Z`;

  return { line, area, coordinates };
}

export function DashboardMarketChart() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [searchValue, setSearchValue] = useState("NIFTY");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<DashboardChartResponse | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const chartData: ChartPoint[] = useMemo(
    () =>
      (response?.points ?? [])
        .map((point) => {
          const value = Number(point.close);
          return Number.isFinite(value) ? { time: point.time, value } : null;
        })
        .filter((point): point is ChartPoint => point !== null),
    [response]
  );

  const latestValue = chartData.length ? chartData[chartData.length - 1].value : null;
  const changePercent = useMemo(() => {
    const first = chartData[0]?.value;
    if (!first || latestValue === null) return null;
    return ((latestValue - first) / first) * 100;
  }, [chartData, latestValue]);

  const { line, area, coordinates } = useMemo(() => buildSvgPath(chartData, 900, 220), [chartData]);

  const xAxisLabels = useMemo(() => {
    if (chartData.length === 0) return [];
    const count = Math.min(6, chartData.length);
    const indices: number[] = [];
    for (let i = 0; i < count; i++) {
      indices.push(Math.round((i * (chartData.length - 1)) / (count - 1)));
    }
    return indices.map((i) => ({
      label: formatTimeLabel(chartData[i].time, response?.interval ?? "day"),
    }));
  }, [chartData, response?.interval]);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDashboardChart(symbol);
      setResponse(data);
      if (!data.points?.length) {
        setError("No Breeze history is available for this symbol.");
      }
    } catch {
      setResponse(null);
      setError("Chart data is temporarily unavailable from Breeze.");
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSymbolChange = () => {
    const normalized = searchValue.trim().toUpperCase();
    if (normalized && normalized !== symbol) {
      setSymbol(normalized);
    }
    setSearchValue(normalized || symbol);
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg || chartData.length === 0) return;
      const rect = svg.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      setMousePos({ x: mouseX, y: mouseY });
      const viewBoxX = (mouseX / rect.width) * 900;
      const xStep = chartData.length > 1 ? 900 / (chartData.length - 1) : 900;
      const index = Math.round(viewBoxX / xStep);
      setHoverIndex(Math.max(0, Math.min(chartData.length - 1, index)));
    },
    [chartData]
  );

  const handleMouseLeave = useCallback(() => {
    setHoverIndex(null);
    setMousePos(null);
  }, []);

  const displaySymbol = response?.resolved.display_symbol ?? symbol;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="min-h-14 gap-3 border-b px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold">{displaySymbol}</div>
          <div className="mt-0.5 text-xs text-muted-foreground tabular-nums">
            {latestValue === null ? (
              "Breeze history"
            ) : (
              <>
                {latestValue.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                <span
                  className={cn(
                    "ml-2 font-medium",
                    (changePercent ?? 0) >= 0 ? "text-green-600 dark:text-green-400" : "text-red-500"
                  )}
                >
                  {(changePercent ?? 0) >= 0 ? "+" : ""}
                  {(changePercent ?? 0).toFixed(2)}%
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex h-8 items-center rounded-md border bg-background pl-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
              onBlur={handleSymbolChange}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSymbolChange();
              }}
              list="dashboard-symbols"
              className="h-7 w-44 border-0 px-2 text-xs shadow-none focus-visible:ring-0"
              aria-label="Select dashboard chart symbol"
            />
            <datalist id="dashboard-symbols">
              {SUGGESTED_SYMBOLS.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>
          {response?.interval ? (
            <span className="inline-flex h-8 items-center rounded-md border px-3 text-xs text-muted-foreground">
              {response.interval}
            </span>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="relative h-[250px] p-0">
        <svg
          ref={svgRef}
          className="h-full w-full px-4 py-3"
          viewBox="0 0 900 220"
          preserveAspectRatio="none"
          aria-label={`${displaySymbol} chart`}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{ cursor: chartData.length > 0 ? "crosshair" : "default" }}
        >
          <defs>
            <linearGradient id="dashboard-chart-area" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#00f2ff" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#00f2ff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0 44H900M0 88H900M0 132H900M0 176H900"
            stroke="currentColor"
            className="text-border"
          />
          {area && <path d={area} fill="url(#dashboard-chart-area)" />}
          {line && (
            <path
              d={line}
              fill="none"
              stroke="#00f2ff"
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
              className="glow-line"
            />
          )}
          {hoverIndex !== null && coordinates[hoverIndex] && (
            <>
              <line
                x1={coordinates[hoverIndex].x}
                y1="0"
                x2={coordinates[hoverIndex].x}
                y2="220"
                stroke="#00f2ff"
                strokeWidth="1"
                strokeDasharray="4 3"
                opacity="0.5"
              />
              <circle
                cx={coordinates[hoverIndex].x}
                cy={coordinates[hoverIndex].y}
                r="4"
                fill="#00f2ff"
                stroke="#0f172a"
                strokeWidth="2"
              />
            </>
          )}
        </svg>

        {xAxisLabels.length > 0 && (
          <div className="pointer-events-none absolute bottom-1 left-4 right-4 flex justify-between">
            {xAxisLabels.map((item, i) => (
              <span
                key={i}
                className="text-[10px] leading-none text-muted-foreground/60 tabular-nums"
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {hoverIndex !== null && mousePos && chartData[hoverIndex] && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border bg-card px-2 py-1.5 text-xs shadow-lg tabular-nums"
            style={{
              left: Math.max(10, Math.min(mousePos.x, 280)),
              top: Math.max(5, Math.min(mousePos.y - 48, 190)),
              transform: "translateX(-50%)",
            }}
          >
            <div className="font-semibold text-foreground">
              {chartData[hoverIndex].value.toLocaleString("en-IN", {
                maximumFractionDigits: 2,
              })}
            </div>
            <div className="text-muted-foreground">
              {formatTooltipTime(chartData[hoverIndex].time)}
            </div>
          </div>
        )}

        {latestValue !== null && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-[#00f2ff] px-2 py-1 text-[11px] font-semibold text-slate-900 tabular-nums">
            {latestValue.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </span>
        )}

        {isLoading && (
          <div className="absolute inset-0 grid place-items-center bg-card/60 text-sm text-muted-foreground backdrop-blur-[1px]">
            Loading Breeze history...
          </div>
        )}
        {!isLoading && error && (
          <div className="absolute inset-x-4 bottom-4 rounded-md border bg-background/95 px-3 py-2 text-xs text-muted-foreground shadow-sm">
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
