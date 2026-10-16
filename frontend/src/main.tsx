import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { bootGooglePageTranslation } from "./lib/googlePageTranslation";

// Google Translate / React DOM Stability Patch
// This prevents React from crashing when Google Translate modifies DOM nodes
const originalRemoveChild = Node.prototype.removeChild;
Node.prototype.removeChild = function <T extends Node>(child: T): T {
  if (child.parentNode !== this) {
    return child;
  }
  return originalRemoveChild.call(this, child);
};

const originalInsertBefore = Node.prototype.insertBefore;
Node.prototype.insertBefore = function <T extends Node>(newNode: T, referenceNode: Node | null): T {
  if (referenceNode && referenceNode.parentNode !== this) {
    return newNode;
  }
  return originalInsertBefore.call(this, newNode, referenceNode);
};

createRoot(document.getElementById("root")!).render(<App />);
bootGooglePageTranslation();

// Production-only: dev HMR must not be cached or intercepted.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => { void navigator.serviceWorker.register("/offline-worker.js").catch(() => {}); });
}
