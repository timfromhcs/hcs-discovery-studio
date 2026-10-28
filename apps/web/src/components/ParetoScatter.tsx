import { useMemo, useState } from "react";
import type { ColumnMeta, ResultItem } from "../api/types";
import { formatNumber } from "../lib/format";

const W = 640;
const H = 330;
const M = { top: 18, right: 24, bottom: 52, left: 62 };

function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) return [min];
  const span = max - min;
  const step0 = span / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(step0)));
  const residual = step0 / magnitude;
  const step = (residual >= 7.5 ? 10 : residual >= 3.5 ? 5 : residual >= 1.5 ? 2 : 1) * magnitude;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = start; value <= max + step * 0.001; value += step) {
    ticks.push(Number(value.toFixed(10)));
  }
  return ticks;
}

export function ParetoScatter({
  items,
  columns,
  onSelect,
}: {
  items: ResultItem[];
  columns: ColumnMeta[];
  onSelect?: (compoundId: string) => void;
}) {
  const numericColumns = columns.filter((column) => column.type === "number");
  const defaults = useMemo(() => {
    const preferred = ["composite_score", "qed", "logp", "mw", "tpsa", "similarity_query"];
    const available = numericColumns.map((column) => column.name);
    const x = preferred.find((name) => available.includes(name) && name !== "composite_score") ?? available[0] ?? "rank";
    const y = available.includes("composite_score") ? "composite_score" : (available[1] ?? "rank");
    return { x, y };
  }, [numericColumns]);

  const [xKey, setXKey] = useState(defaults.x);
  const [yKey, setYKey] = useState(defaults.y);

  const points = useMemo(() => {
    return items
      .map((item) => {
        const x = Number(item.metrics?.[xKey] ?? (xKey === "rank" ? item.rank : xKey === "composite_score" ? item.composite_score : null));
        const y = Number(item.metrics?.[yKey] ?? (yKey === "rank" ? item.rank : yKey === "composite_score" ? item.composite_score : null));
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        return { item, x, y };
      })
      .filter((value): value is { item: ResultItem; x: number; y: number } => value !== null);
  }, [items, xKey, yKey]);

  if (!numericColumns.length) {
    return <div className="graph-empty">This run has no numeric result columns to plot.</div>;
  }

  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xPad = xMin === xMax ? Math.max(1, Math.abs(xMin) * 0.1) : (xMax - xMin) * 0.06;
  const yPad = yMin === yMax ? Math.max(1, Math.abs(yMin) * 0.1) : (yMax - yMin) * 0.08;
  const plotW = W - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const sx = (value: number) => M.left + ((value - (xMin - xPad)) / (xMax - xMin + 2 * xPad)) * plotW;
  const sy = (value: number) => M.top + plotH - ((value - (yMin - yPad)) / (yMax - yMin + 2 * yPad)) * plotH;
  const xTicks = niceTicks(xMin - xPad, xMax + xPad);
  const yTicks = niceTicks(yMin - yPad, yMax + yPad);
  const xMeta = numericColumns.find((column) => column.name === xKey);
  const yMeta = numericColumns.find((column) => column.name === yKey);

  if (!points.length) {
    return <div className="graph-empty">No rows have values for both selected columns.</div>;
  }

  return (
    <div className="scatter">
      <div className="scatter-controls">
        <label>
          <span>X axis</span>
          <select className="input select" value={xKey} onChange={(event) => setXKey(event.target.value)}>
            {numericColumns.map((column) => (
              <option key={column.name} value={column.name}>
                {column.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Y axis</span>
          <select className="input select" value={yKey} onChange={(event) => setYKey(event.target.value)}>
            {numericColumns.map((column) => (
              <option key={column.name} value={column.name}>
                {column.label}
              </option>
            ))}
          </select>
        </label>
        <span className="scatter-legend">
          <span className="legend-dot front" /> Pareto front 1
          <span className="legend-dot rejected" /> Filtered out
          <span className="legend-dot normal" /> Other
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="scatter-svg" role="img" aria-label={`Scatter plot of ${xMeta?.label ?? xKey} versus ${yMeta?.label ?? yKey}`}>
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={M.left} x2={W - M.right} y1={sy(tick)} y2={sy(tick)} className="chart-grid" />
            <text x={M.left - 10} y={sy(tick)} className="chart-tick" textAnchor="end" dominantBaseline="middle">
              {formatNumber(tick, 2)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={sx(tick)} x2={sx(tick)} y1={M.top} y2={H - M.bottom} className="chart-grid" />
            <text x={sx(tick)} y={H - M.bottom + 18} className="chart-tick" textAnchor="middle">
              {formatNumber(tick, 2)}
            </text>
          </g>
        ))}
        <line x1={M.left} x2={M.left} y1={M.top} y2={H - M.bottom} className="chart-axis" />
        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} className="chart-axis" />
        <text x={W / 2} y={H - 10} className="chart-axis-label" textAnchor="middle">
          {xMeta?.label ?? xKey}
          {xMeta?.unit ? ` (${xMeta.unit})` : ""}
        </text>
        <text transform={`translate(14 ${H / 2}) rotate(-90)`} className="chart-axis-label" textAnchor="middle">
          {yMeta?.label ?? yKey}
          {yMeta?.unit ? ` (${yMeta.unit})` : ""}
        </text>
        {points.map(({ item, x, y }) => {
          const front = item.pareto_front === 1;
          const normal = !item.rejected && !front;
          const className = item.rejected ? "point rejected" : front ? "point front" : normal ? "point normal" : "point";
          return (
            <circle
              key={item.compound_id}
              cx={sx(x)}
              cy={sy(y)}
              r={item.rejected ? 3.2 : 4.2}
              className={className}
              tabIndex={onSelect ? 0 : undefined}
              role={onSelect ? "link" : undefined}
              aria-label={`${item.name ?? item.compound_id}: ${formatNumber(x)}, ${formatNumber(y)}${item.rejected ? ", filtered" : ""}`}
              onClick={() => onSelect?.(item.compound_id)}
              onKeyDown={(event) => {
                if (onSelect && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onSelect(item.compound_id);
                }
              }}
            >
              <title>
                {item.name ?? item.compound_id}
                {"\n"}
                {xMeta?.label ?? xKey}: {formatNumber(x)}
                {"\n"}
                {yMeta?.label ?? yKey}: {formatNumber(y)}
                {item.rejected ? "\nFiltered out" : item.pareto_front === 1 ? "\nPareto front 1" : ""}
              </title>
            </circle>
          );
        })}
      </svg>
    </div>
  );
}
