import { useMemo } from "react";
import type { NodeStatus, WorkflowDefinition, WorkflowEdge } from "../api/types";

const NODE_W = 190;
const NODE_H = 64;
const GAP_X = 64;
const GAP_Y = 22;
const PAD = 20;

interface Placement {
  id: string;
  title: string;
  type: string;
  x: number;
  y: number;
  layer: number;
  row: number;
}

function layout(definition: WorkflowDefinition): { nodes: Placement[]; edges: WorkflowEdge[]; width: number; height: number } {
  const ids = definition.nodes.map((node) => node.id);
  const incoming = new Map<string, string[]>(ids.map((id) => [id, []]));
  const outgoing = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const edge of definition.edges) {
    if (!incoming.has(edge.target) || !outgoing.has(edge.source)) continue;
    incoming.get(edge.target)?.push(edge.source);
    outgoing.get(edge.source)?.push(edge.target);
  }
  const depth = new Map<string, number>();
  const visit = (id: string, stack: Set<string>): number => {
    if (depth.has(id)) return depth.get(id) ?? 0;
    if (stack.has(id)) return 0;
    stack.add(id);
    const parents = incoming.get(id) ?? [];
    const value = parents.length ? Math.max(...parents.map((parent) => visit(parent, stack) + 1)) : 0;
    stack.delete(id);
    depth.set(id, value);
    return value;
  };
  ids.forEach((id) => visit(id, new Set()));

  const layers = new Map<number, string[]>();
  for (const id of ids) {
    const level = depth.get(id) ?? 0;
    layers.set(level, [...(layers.get(level) ?? []), id]);
  }
  const maxRows = Math.max(1, ...Array.from(layers.values(), (layer) => layer.length));
  const nodeById = new Map(definition.nodes.map((node) => [node.id, node]));
  const nodes: Placement[] = [];
  for (const [layer, layerIds] of Array.from(layers.entries()).sort((a, b) => a[0] - b[0])) {
    layerIds.forEach((id, row) => {
      const node = nodeById.get(id);
      if (!node) return;
      const offset = ((maxRows - layerIds.length) * (NODE_H + GAP_Y)) / 2;
      nodes.push({
        id,
        title: node.title || node.type,
        type: node.type,
        layer,
        row,
        x: PAD + layer * (NODE_W + GAP_X),
        y: PAD + offset + row * (NODE_H + GAP_Y),
      });
    });
  }
  const width = PAD * 2 + (Math.max(...layers.keys(), 0) + 1) * NODE_W + Math.max(0, layers.size - 1) * GAP_X;
  const height = PAD * 2 + maxRows * NODE_H + Math.max(0, maxRows - 1) * GAP_Y;
  return { nodes, edges: definition.edges, width, height };
}

export function WorkflowGraph({
  definition,
  statuses,
  selectedId,
  onSelect,
  ariaLabel = "Workflow dependency graph",
}: {
  definition: WorkflowDefinition;
  statuses?: Record<string, NodeStatus>;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  ariaLabel?: string;
}) {
  const { nodes, edges, width, height } = useMemo(() => layout(definition), [definition]);
  const byId = new Map(nodes.map((node) => [node.id, node]));

  if (!definition.nodes.length) {
    return <div className="graph-empty">This workflow has no nodes yet.</div>;
  }

  return (
    <div className="workflow-graph">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={ariaLabel} style={{ minWidth: Math.min(width, 720) }}>
        <defs>
          <marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border-strong)" />
          </marker>
        </defs>
        <g className="graph-edges">
          {edges.map((edge) => {
            const source = byId.get(edge.source);
            const target = byId.get(edge.target);
            if (!source || !target) return null;
            const x1 = source.x + NODE_W;
            const y1 = source.y + NODE_H / 2;
            const x2 = target.x;
            const y2 = target.y + NODE_H / 2;
            const curve = Math.max(24, (x2 - x1) / 2);
            return (
              <path
                key={`${edge.source}-${edge.target}`}
                d={`M ${x1} ${y1} C ${x1 + curve} ${y1}, ${x2 - curve} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="var(--border-strong)"
                strokeWidth={1.5}
                markerEnd="url(#graph-arrow)"
              />
            );
          })}
        </g>
        <g className="graph-nodes">
          {nodes.map((node) => {
            const status = statuses?.[node.id] ?? "pending";
            const selected = selectedId === node.id;
            return (
              <g
                key={node.id}
                className={`graph-node status-${status} ${selected ? "selected" : ""} ${onSelect ? "clickable" : ""}`}
                transform={`translate(${node.x} ${node.y})`}
                role={onSelect ? "button" : undefined}
                tabIndex={onSelect ? 0 : undefined}
                aria-label={`${node.title}, ${node.type}, ${status}`}
                onClick={() => onSelect?.(node.id)}
                onKeyDown={(event) => {
                  if (onSelect && (event.key === "Enter" || event.key === " ")) {
                    event.preventDefault();
                    onSelect(node.id);
                  }
                }}
              >
                <rect width={NODE_W} height={NODE_H} rx={10} className="graph-node-box" />
                <rect width={4} height={NODE_H} rx={2} className="graph-node-accent" />
                <text x={16} y={25} className="graph-node-title">
                  {node.title.length > 22 ? `${node.title.slice(0, 21)}…` : node.title}
                </text>
                <text x={16} y={45} className="graph-node-type">
                  {node.type}
                </text>
                <g transform={`translate(${NODE_W - 22} 18)`} className="graph-node-status">
                  <circle r={5} />
                </g>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
