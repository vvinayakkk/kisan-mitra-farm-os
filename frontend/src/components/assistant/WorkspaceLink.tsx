import { Link, useNavigate } from "react-router-dom";
import { flushSync } from "react-dom";
import "./workspace-link.css";
export function WorkspaceLink({ to }: { to: string }) {
  const navigate = useNavigate();
  return (
    <Link
      to={to}
      className="classic-workspace-entry"
      aria-label="Switch to new interface"
      onClick={(event) => {
        if (
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey ||
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
        )
          return;
        const page = document as Document & {
          startViewTransition?: (callback: () => void) => unknown;
        };
        if (page.startViewTransition) {
          event.preventDefault();
          page.startViewTransition(() => flushSync(() => navigate(to)));
        }
      }}
    >
      ✦ New interface
    </Link>
  );
}
