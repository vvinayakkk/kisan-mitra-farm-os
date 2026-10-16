import type { ComponentProps, ReactNode } from "react";
import { VoiceInput } from "./VoiceInput";
import "./workspace-voice-field.css";

type Props = Omit<ComponentProps<typeof VoiceInput>, "className"> & {
  children: ReactNode;
};

/** Keep dictation with its field without adding another grid cell or form row. */
export function WorkspaceVoiceField({ children, ...voice }: Props) {
  return (
    <div className="workspace-voice-field">
      {children}
      <VoiceInput {...voice} className="workspace-field-mic" />
    </div>
  );
}
