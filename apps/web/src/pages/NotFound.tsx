import { Link } from "react-router-dom";
import { LinkButton } from "../components/ui";

export function NotFoundPage() {
  return (
    <div className="page not-found">
      <div className="not-found-card">
        <span className="not-found-code mono">404</span>
        <h1>This view does not exist</h1>
        <p className="muted">
          The route is not part of this build. A deep link to a deleted project or run will also land here, because the
          local API returns an empty workspace rather than a fabricated record.
        </p>
        <div className="not-found-actions">
          <LinkButton to="/" variant="primary" icon="workspace">
            Back to workspace
          </LinkButton>
          <Link className="text-link" to="/about">
            About & help
          </Link>
        </div>
      </div>
    </div>
  );
}
