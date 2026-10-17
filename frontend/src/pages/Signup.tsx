import { Navigate } from "react-router-dom";

// Phone verification resolves both new and existing farmers. Setup happens only
// after loading the owned database profile, so registering on another device
// cannot overwrite details previously saved in the app.
export default function Signup() {
  return <Navigate to="/login" replace />;
}
