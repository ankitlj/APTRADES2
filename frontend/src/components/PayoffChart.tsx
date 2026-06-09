import type { PayoffResponse } from "../lib/api";

function fmt(v: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(v);
}

export function PayoffChart({ payoff, uid }: { payoff: PayoffResponse; uid: string }) {
  const W = 600;
  const H = 220;
  const PAD = 44;
  const plotW = W - PAD * 2;
  const plotH = H - PAD * 2;

  const spots = payoff.curve.map((p) => p.spot);
  const pnls = payoff.curve.map((p) => p.pnl);
  const minSpot = Math.min(...spots);
  const maxSpot = Math.max(...spots);
  const minPnl = Math.min(...pnls);
  const maxPnl = Math.max(...pnls);
  const spotRange = maxSpot - minSpot || 1;
  const pnlRange = maxPnl - minPnl || 1;

  const sx = (s: number) => PAD + ((s - minSpot) / spotRange) * plotW;
  const sy = (p: number) => PAD + plotH - ((p - minPnl) / pnlRange) * plotH;

  const pts = payoff.curve.map((p) => `${sx(p.spot).toFixed(1)},${sy(p.pnl).toFixed(1)}`).join(" ");
  const zeroY = sy(0);
  const areaPoints = `${sx(minSpot).toFixed(1)},${zeroY.toFixed(1)} ${pts} ${sx(maxSpot).toFixed(1)},${zeroY.toFixed(1)}`;

  const aboveId = `az-${uid}`;
  const belowId = `bz-${uid}`;

  return (
    <div className="payoff-chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="payoff-svg" aria-label="Payoff diagram">
        <defs>
          <clipPath id={aboveId}>
            <rect x="0" y="0" width={W} height={zeroY} />
          </clipPath>
          <clipPath id={belowId}>
            <rect x="0" y={zeroY} width={W} height={H} />
          </clipPath>
        </defs>

        <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke="#9ca3af" strokeDasharray="4 3" strokeWidth="1" />

        <polygon points={areaPoints} fill="rgba(21,128,61,0.14)" clipPath={`url(#${aboveId})`} />
        <polygon points={areaPoints} fill="rgba(220,38,38,0.12)" clipPath={`url(#${belowId})`} />

        <polyline points={pts} fill="none" stroke="#1d4ed8" strokeWidth="1.8" strokeLinejoin="round" />

        {payoff.breakevens.map((be) => (
          <g key={be}>
            <line x1={sx(be)} y1={PAD} x2={sx(be)} y2={H - PAD} stroke="#b45309" strokeDasharray="3 3" strokeWidth="1" />
            <text x={sx(be)} y={PAD - 4} textAnchor="middle" fontSize="9" fill="#b45309">
              {fmt(be)}
            </text>
          </g>
        ))}

        {[minSpot, (minSpot + maxSpot) / 2, maxSpot].map((s) => (
          <g key={s}>
            <line x1={sx(s)} y1={H - PAD} x2={sx(s)} y2={H - PAD + 4} stroke="#9ca3af" strokeWidth="1" />
            <text x={sx(s)} y={H - PAD + 16} textAnchor="middle" fontSize="10" fill="#5b6472">
              {fmt(s)}
            </text>
          </g>
        ))}

        <text x={PAD - 6} y={zeroY + 4} textAnchor="end" fontSize="10" fill="#5b6472">
          0
        </text>
      </svg>
    </div>
  );
}
