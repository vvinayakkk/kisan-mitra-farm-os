import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useRef, useState } from "react";
import { Check, Languages, Phone, X } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { SUPPORT_HOTLINE } from "@/components/CallAgentButton";
import "./workspace-header-actions.css";

import { APP_LANGUAGES as languages } from "@/lib/languagePreference";

export function WorkspaceHeaderActions() {
  const { language, setLanguage, isLoadingLanguage } = useLanguage();
  const [callOpen, setCallOpen] = useState(false);
  const callButton = useRef<HTMLButtonElement>(null);
  return (
    <div className="workspace-header-actions" aria-label="Language and call support">
      <Dropdown.Root>
        <Dropdown.Trigger disabled={isLoadingLanguage} className="workspace-utility" aria-label="Change language" data-tooltip="Change language">
          <Languages size={15} aria-hidden="true" />
          <span className="notranslate" translate="no">{language.toUpperCase()}</span>
        </Dropdown.Trigger>
        <Dropdown.Portal>
          <Dropdown.Content className="workspace-language-menu" align="end" sideOffset={8}>
            <Dropdown.Label>Language for chat & voice</Dropdown.Label>
            <Dropdown.RadioGroup value={language} onValueChange={(value) => {
              const selected = languages.find(([code]) => code === value);
              if (selected && selected[0] !== language) setLanguage(selected[0]);
            }}>
              {languages.map(([code, label]) => (
                <Dropdown.RadioItem key={code} value={code} className="notranslate" translate="no">
                  <span>{label}</span>
                  <Dropdown.ItemIndicator><Check size={14} /></Dropdown.ItemIndicator>
                </Dropdown.RadioItem>
              ))}
            </Dropdown.RadioGroup>
          </Dropdown.Content>
        </Dropdown.Portal>
      </Dropdown.Root>
      {callOpen ? (
        <div className="workspace-call-inline" aria-label="Support telephone">
          <a className="notranslate" translate="no" href={`tel:${SUPPORT_HOTLINE.replace(/[^+\d]/g, "")}`}>
            {SUPPORT_HOTLINE}
          </a>
          <button aria-label="Close call support" onClick={() => {
            setCallOpen(false);
            requestAnimationFrame(() => callButton.current?.focus());
          }}><X size={13} /></button>
        </div>
      ) : (
        <button ref={callButton} className="workspace-utility" aria-label="Call support agent" aria-expanded={false} data-tooltip="Call support agent" onClick={() => setCallOpen(true)}>
          <Phone size={15} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
