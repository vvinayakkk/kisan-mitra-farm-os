import { useState } from "react";
import { ChevronDown, Leaf } from "lucide-react";
import { AssistantChat } from "./AssistantChat";
import type { FarmContext } from "./suggestions";

export function MitraHelper({
  context,
  selectedDate,
  collapsible = false,
  className = "",
  weatherCity,
}: {
  context: FarmContext;
  selectedDate?: string;
  collapsible?: boolean;
  className?: string;
  weatherCity?: string;
}) {
  const [open, setOpen] = useState(!collapsible);
  const heading = (
    <>
      <Leaf size={15} />
      <strong>A little help from Mitra</strong>
      {collapsible && (
        <ChevronDown size={14} className={open ? "helper-chevron-open" : ""} />
      )}
    </>
  );
  return (
    <section
      className={`mitra-page-helper ${className}`}
      aria-label="A little help from Mitra"
    >
      {collapsible ? (
        <button
          className="mitra-helper-heading"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
        >
          {heading}
        </button>
      ) : (
        <header className="mitra-helper-heading">{heading}</header>
      )}
      <div hidden={!open}>
        <AssistantChat
          compact
          minimal
          context={context}
          selectedDate={selectedDate}
          weatherCity={weatherCity}
        />
      </div>
    </section>
  );
}
