import { Navigate } from "react-router-dom";

// The old public table browser is replaced by verified administration.
export default function DatabaseExplorer() {
  return <Navigate to="/control" replace />;
}
