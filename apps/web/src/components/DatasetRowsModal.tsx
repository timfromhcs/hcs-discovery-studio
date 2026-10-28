import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { DatasetSummary } from "../api/types";
import { formatDate } from "../lib/format";
import { Badge, Button, EmptyState, ErrorState, KeyValue, Modal, Skeleton, Tabs } from "./ui";

type RowFilter = "all" | "imported" | "error" | "duplicate";

export function DatasetRowsModal({
  dataset,
  open,
  onClose,
}: {
  dataset: DatasetSummary | null;
  open: boolean;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<RowFilter>("all");
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const rows = useQuery({
    queryKey: ["dataset", dataset?.id, "rows", filter, offset],
    queryFn: () =>
      api.datasets.rows(dataset?.id ?? "", {
        status: filter === "all" ? undefined : filter,
        limit,
        offset,
      }),
    enabled: open && Boolean(dataset),
  });

  if (!dataset) return null;
  const total = rows.data?.total ?? 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={dataset.name}
      description="Every source row is retained. Errors are shown verbatim with their row index."
      width="xl"
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="form-stack">
        <KeyValue
          items={[
            { label: "Dataset ID", value: dataset.id, mono: true },
            { label: "Format", value: dataset.source_format },
            { label: "Source file", value: dataset.original_filename, mono: true },
            { label: "Imported", value: `${dataset.imported_count} / ${dataset.record_count}` },
            { label: "Errors", value: dataset.error_count },
            { label: "Duplicates", value: dataset.duplicate_count },
            { label: "License", value: dataset.license },
            { label: "Created", value: formatDate(dataset.created_at) },
            { label: "SHA-256", value: dataset.sha256, mono: true },
            { label: "Source URL", value: dataset.source_url ?? "—", mono: true },
          ]}
        />

        <div className="row-between">
          <Tabs<RowFilter>
            label="Filter dataset rows"
            value={filter}
            onChange={(value) => {
              setFilter(value);
              setOffset(0);
            }}
            tabs={[
              { id: "all", label: "All", count: dataset.record_count },
              { id: "imported", label: "Imported", count: dataset.imported_count },
              { id: "error", label: "Errors", count: dataset.error_count },
              { id: "duplicate", label: "Duplicates", count: dataset.duplicate_count },
            ]}
          />
          <span className="muted small tabular">
            {total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}` : "0 rows"}
          </span>
        </div>

        {rows.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : rows.error ? (
          <ErrorState error={rows.error} onRetry={() => void rows.refetch()} />
        ) : rows.data?.items.length ? (
          <div className="table-wrap tall">
            <table className="data-table compact-table">
              <thead>
                <tr>
                  <th className="num">Row</th>
                  <th>Status</th>
                  <th>Source values</th>
                  <th>Linked compound</th>
                </tr>
              </thead>
              <tbody>
                {rows.data.items.map((row) => (
                  <tr key={row.row_index}>
                    <td className="num tabular">{row.row_index}</td>
                    <td>
                      <Badge tone={row.status === "imported" ? "ok" : row.status === "error" ? "danger" : "warn"}>
                        {row.status}
                      </Badge>
                    </td>
                    <td>
                      <div className="raw-cell">
                        {Object.entries(row.raw).map(([key, value]) => (
                          <span key={key}>
                            <em>{key}:</em> {value === null || value === undefined ? "—" : String(value)}
                          </span>
                        ))}
                      </div>
                      {row.error ? <p className="error-text small row-error">{row.error}</p> : null}
                    </td>
                    <td className="mono small">{row.compound_id ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState compact title="No rows in this filter" description="Try the All tab or re-import the dataset." />
        )}

        {total > limit ? (
          <div className="pagination">
            <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              Previous
            </Button>
            <span className="muted small tabular">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
            </span>
            <Button
              size="sm"
              variant="secondary"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
