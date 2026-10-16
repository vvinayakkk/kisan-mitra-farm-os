import { useNavigate } from 'react-router-dom';
import { VoiceInput } from './VoiceInput';


export function VoiceAssistantButton() {
  const navigate = useNavigate();
  return <div style={{ position: 'fixed', bottom: 26, left: 24, zIndex: 80, color: '#536c45', background: '#fbfcf7', border: '1px solid #ced9c4', borderRadius: 16, boxShadow: '0 6px 24px rgba(30,50,30,.12)' }}>
    <VoiceInput label="Speak to Mitra" onTranscript={voiceDraft => navigate('/workspace?view=chat', { state: { voiceDraft } })} />
  </div>;
}
