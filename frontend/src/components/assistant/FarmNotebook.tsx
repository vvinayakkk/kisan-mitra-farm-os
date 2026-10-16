import { useId, useRef, type ReactNode } from "react";
import { ArrowLeft, ArrowRight, Leaf } from "lucide-react";
import type { NotebookTab } from "./FarmWorkspace";
import { MitraHelper } from "./MitraHelper";
import { PreparedBySaathi } from "./PreparedBySaathi";
import type { FarmContext } from "./suggestions";
import "./farm-notebook.css";

export const notebookSections: [NotebookTab, string][] = [
  ["today", "Today"], ["fields", "My fields"], ["ledger", "Money"],
  ["cases", "Crop follow-ups"], ["missions", "Plans"], ["memory", "Memory"], ["files", "Files"],
];

export function FarmNotebook({ tab, onChange, children }: {
  tab: NotebookTab; onChange: (tab: NotebookTab) => void; children: ReactNode;
}) {
  const id = useId();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const index = notebookSections.findIndex(([key]) => key === tab);
  const context = tab === "cases" ? "followups" : tab === "files" ? "records" : tab as FarmContext;
  return (
    <section className="farm-journal" aria-label="Farm notebook">
      <header className="journal-masthead"><div><Leaf size={19} /><h1>My farm notebook</h1></div><span>A little care, every day.</span></header>
      <div className="journal-book">
        <aside className="journal-contents">
          <div className="journal-mitra-intro"><span>WRITE IT WITH MITRA</span><p>Say what happened on your farm. Mitra can turn it into a note, a cost or a plan for you to review.</p></div>
          <MitraHelper context={context} className="journal-helper" />
          <div className="journal-tabs" role="tablist" aria-label="Farm notebook sections" aria-orientation="vertical">
            {notebookSections.map(([key, label], i) => <button key={key} ref={el => { buttons.current[i] = el; }} type="button" role="tab" id={`${id}-${key}`} aria-selected={key === tab} aria-controls={`${id}-page`} tabIndex={key === tab ? 0 : -1} onClick={() => onChange(key)} onKeyDown={e => {
              const next = e.key === "Home" ? 0 : e.key === "End" ? notebookSections.length - 1 : e.key === "ArrowDown" || e.key === "ArrowRight" ? (i + 1) % notebookSections.length : e.key === "ArrowUp" || e.key === "ArrowLeft" ? (i + notebookSections.length - 1) % notebookSections.length : -1;
              if (next >= 0) { e.preventDefault(); onChange(notebookSections[next][0]); buttons.current[next]?.focus(); }
            }}><span className="journal-tab-number">{String(i + 1).padStart(2, "0")}</span><span>{label}</span><ArrowRight size={14} /></button>)}
          </div>
          <Leaf className="journal-leaf" size={58} strokeWidth={0.8} aria-hidden="true" />
        </aside>
        <div className="journal-binding" aria-hidden="true">{Array.from({length: 12}, (_, i) => <i key={i} />)}</div>
        <div className="journal-sheet">
          <div className="journal-running-head"><span>{notebookSections[index][1]}</span><span>MY FARM JOURNAL</span></div>
          <PreparedBySaathi area="records" />
          <div key={tab} className="journal-page-turn" role="tabpanel" id={`${id}-page`} aria-labelledby={`${id}-${tab}`} tabIndex={0}>{children}</div>
          <footer className="journal-pagination"><button type="button" aria-label="Previous notebook page" disabled={index === 0} onClick={() => onChange(notebookSections[index - 1][0])}><ArrowLeft size={16} /><span>Previous</span></button><span aria-live="polite">{index + 1} / {notebookSections.length}</span><button type="button" aria-label="Next notebook page" disabled={index === notebookSections.length - 1} onClick={() => onChange(notebookSections[index + 1][0])}><span>Next</span><ArrowRight size={16} /></button></footer>
        </div>
      </div>
    </section>
  );
}
