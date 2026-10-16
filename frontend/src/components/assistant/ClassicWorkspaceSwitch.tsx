import { useLocation } from "react-router-dom";
import { WorkspaceLink } from "./WorkspaceLink";
import { workspaceDestination } from "@/lib/workspaceNavigation";
export function ClassicWorkspaceSwitch() {
  const { pathname } = useLocation();
  const to = workspaceDestination(pathname);
  return to ? <WorkspaceLink to={to} /> : null;
}
