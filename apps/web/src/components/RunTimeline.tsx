import type { RunDetail } from "../api/types";
import { formatDuration } from "../lib/format";

/**
 * Run timeline built from the persisted timestamps only.
 *
 * The point is to make the invisible parts of a run visible: how long it waited in
 * the queue, how long each node took, and which nodes were served from cache. Nothing
 * here is estimated from the browser clock; a segment without a recorded start is
 * left out instead of being invented.
 */

interface Segment {
  id: string;
  label: string;
  status: string;
  start: number;
  end: number;
  cached: boolean;
}

function toMs(value: string | null | undefined): number | null {
  if (!value) return null;
  const normalised = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  const parsed = Date.parse(normalised);
  return Number.isFinite(parsed) ? parsed : null;
}

export function RunTimeline({ run }: { run: RunDetail }) {
  const created = toMs(run.created_at);
  const finished = toMs(run.finished_at);
  const now = Date.now();
  const started = toMs(run.started_at);

  if (created === null) {
    return <p className="muted small">This run has no creation timestamp, so no timeline can be drawn.</p>;
  }

  const segments: Segment[] = [];
  if (started !== null && started > created) {
    segments.push({
      id: "queue",
      label: "queue",
      status: "queued",
      start: created,
      end: started,
      cached: false,
    });
  }
  for (const node of run.nodes) {
    const nodeStart = toMs(node.started_at);
    const nodeEnd = toMs(node.finished_at) ?? (node.status === "running" ? now : null);
    if (nodeStart === null || nodeEnd === null || nodeEnd < nodeStart) continue;
    segments.push({
      id: node.node_id,
      label: node.node_id,
      status: node.cached ? "cached" : node.status,
      start: nodeStart,
      end: nodeEnd,
      cached: node.cached,
    });
  }

  const end = finished ?? (run.status === "running" ? now : mathMax([...segments.map((s) => s.end), created]));
  const total = Math.max(end - created, 1);
  const queueMs = started !== null ? Math.max(started - created, 0) : 0;
  const workMs = segments.filter((s) => s.id !== "queue").reduce((sum, s) => sum + (s.end - s.start), 0);

  return (
    <section className="run-timeline" aria-label="Run timeline" data-testid="run-timeline">
      <div className="timeline-head">
        <span className="eyebrow">Timeline</span>
        <span className="muted tiny">
          {formatDuration(queueMs)} queued · {formatDuration(workMs)} in nodes · {formatDuration(end - created)} total
        </span>
      </div>
      {segments.length === 0 ? (
        <p className="muted small">No node timing was recorded for this run.</p>
      ) : (
        <ol className="timeline-rows">
          {segments.map((segment) => {
            const left = ((segment.start - created) / total) * 100;
            const width = Math.max(((segment.end - segment.start) / total) * 100, 1.5);
            return (
              <li key={segment.id} className={`timeline-row status-${segment.status}`}>
                <span className="timeline-label mono tiny" title={segment.label}>
                  {segment.label}
                </span>
                <span className="timeline-track" aria-hidden="true">
                  <span
                    className="timeline-bar"
                    style={{ left: `${Math.min(Math.max(left, 0), 100)}%`, width: `${width}%` }}
                  />
                </span>
                <span className="timeline-meta tiny muted">
                  {formatDuration(segment.end - segment.start)}
                  {segment.cached ? " · cache" : ""}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function mathMax(values: number[]): number {
  return values.reduce((best, value) => (value > best ? value : best), 0);
}
