import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ResearchSources } from "./ResearchSources";
afterEach(cleanup);
it("renders only HTTP sources with protected external links", () => {
  render(<ResearchSources result={{available: true, answer: "A sourced recommendation.", sources: [
    {id: 1, title: "Official guidance", url: "https://agri.gov.in/advice"},
    {id: 2, title: "Other source", url: "HTTP://example.com/report"},
    {id: 3, title: "Unsafe script", url: "javascript:alert(1)"},
    {id: 4, title: "Embedded data", url: "data:text/html,unsafe"},
    {id: 5, title: "Relative source", url: "/internal"},
  ]}}/>);
  expect(screen.getByText("Research & sources · 2")).toBeInTheDocument();
  const link = screen.getByText("Official guidance").closest("a")!;
  expect(link).toHaveAttribute("href", "https://agri.gov.in/advice"); expect(link).toHaveAttribute("target", "_blank"); expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(screen.queryByText("Unsafe script")).not.toBeInTheDocument(); expect(screen.queryByText("Embedded data")).not.toBeInTheDocument(); expect(screen.queryByText("Relative source")).not.toBeInTheDocument();
});
it("isolates provider HTML in a sandbox without scripts or same-origin access", () => {
  const html = '<p>Search suggestions</p><script>window.parent.alert(1)</script>';
  render(<ResearchSources result={{available: true, search_suggestions_html: html}}/>);
  const frame = screen.getByTitle("Google Search suggestions");
  const sandbox = frame.getAttribute("sandbox")!.split(" ");
  expect(sandbox).not.toContain("allow-scripts"); expect(sandbox).not.toContain("allow-same-origin"); expect(sandbox).not.toContain("allow-top-navigation");
  expect(frame).toHaveAttribute("referrerpolicy", "no-referrer"); expect(frame).toHaveAttribute("srcdoc", html);
});
it("explains unavailable research instead of presenting unsupported findings", () => {
  render(<ResearchSources result={{available: false, answer: "Unverified finding", sources: [{id: 1, title: "Old source", url: "https://example.com"}]}}/>);
  expect(screen.getByText(/Web research is unavailable right now/)).toBeInTheDocument();
  expect(screen.queryByText("Unverified finding")).not.toBeInTheDocument(); expect(screen.queryByText("Old source")).not.toBeInTheDocument();
});
