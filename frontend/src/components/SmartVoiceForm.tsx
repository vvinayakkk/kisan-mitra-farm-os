import { apiFetch } from '@/lib/apiClient';
import { useState } from 'react';
import { VoiceInput } from './VoiceInput';
import { Loader2 } from 'lucide-react';

interface SmartVoiceFormProps {
  title: string;
  description: string;
  endpoint: string;
  onDataExtracted: (data: Record<string, unknown>) => void;
  lang?: string;
}


export function SmartVoiceForm({ title, description, onDataExtracted, lang = 'en-IN' }: SmartVoiceFormProps) {
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  async function extract(transcript: string) {
    setProcessing(true); setError('');
    try {
      const response = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/profile/voice-update`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transcript }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Your details could not be extracted. Nothing was saved.');
      onDataExtracted(body.identified_fields || {});
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Voice extraction is unavailable. You can fill in the fields.'); }
    finally { setProcessing(false); }
  }
  return <div className="rounded-2xl border border-emerald-200/60 p-4">
    {title && <h3 className="text-sm font-medium">{title}</h3>}
    {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
    <div className="flex items-center gap-3"><VoiceInput label="Speak your farm details" language={lang} disabled={processing} onTranscript={text => void extract(text)} /><span className="text-xs text-muted-foreground">{processing ? <span className="flex gap-2 items-center"><Loader2 size={14} className="animate-spin" />Preparing editable fields</span> : 'Speak your details · review before saving'}</span></div>
    {error && <p role="alert" className="text-xs text-red-700 mt-2">{error}</p>}
  </div>;
}
