import { apiFetch } from "@/lib/apiClient";
import { useState, useRef, useEffect } from "react";
import { useTheme } from "next-themes";
import { FarmBackground, GlassSection } from "@/components/FarmTheme";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { VoiceInput } from "@/components/VoiceInput";
import { SpeechPlayback } from "@/components/SpeechPlayback";
import { useLanguage } from "@/contexts/LanguageContext";
import { Send, Mic, Volume2, VolumeX, Loader2 } from "lucide-react";

const translations = {
  en: {
    title: "Ask Me Anything",
    description: "Ask any question and get instant answers powered by AI.",
    inputPlaceholder: "Type your question here...",
    send: "Send",
    listen: "Listen",
    speaking: "Speaking...",
    thinking: "Thinking..."
  },
  hi: {
    title: "मुझसे कुछ भी पूछें",
    description: "कोई भी सवाल पूछें और AI द्वारा संचालित तत्काल उत्तर पाएं।",
    inputPlaceholder: "अपना सवाल यहाँ लिखें...",
    send: "भेजें",
    listen: "सुनें",
    speaking: "बोल रहा है...",
    thinking: "सोच रहा है..."
  }
};

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function Chat() {
  const { language } = useLanguage();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const t = translations[language as keyof typeof translations] || translations.en;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: text,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      // Call the chat API
      const API_URL = import.meta.env.VITE_API_URL || '';
      const response = await apiFetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });

      const data = await response.json();

      // Add assistant response
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.response || "I couldn't generate a response. Please try again.",
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !loading) {
      sendMessage(input);
    }
  };

  return (
    <div style={{ minHeight: '100vh', position: 'relative' }}>
      <FarmBackground />
      
      <div style={{ position: 'relative', zIndex: 50 }}>
        <DashboardHeader lastUpdateSeconds={0} sensorNodeOnline={true} />
      </div>

      <main style={{ position: 'relative', zIndex: 10, maxWidth: '900px', margin: '0 auto', padding: '32px 20px 60px' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px', textAlign: 'center' }}>
          <h1 style={{
            fontSize: '36px', fontWeight: 800, fontFamily: "'Nunito', sans-serif",
            color: isDark ? '#A8D89A' : '#1B3A20', marginBottom: '8px'
          }}>
             {t.title}
          </h1>
          <p style={{ fontSize: '15px', color: isDark ? '#A3B8A8' : '#2C3E30' }}>
            {t.description}
          </p>
        </div>

        {/* Chat Container */}
        <GlassSection title="">
          <div style={{
            height: '500px', overflow: 'auto',
            marginBottom: '20px', paddingRight: '8px'
          }}>
            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', paddingTop: '100px', color: isDark ? '#6A8A6A' : '#888' }}>
                <p style={{ fontSize: '18px', marginBottom: '10px' }}> Start a conversation!</p>
                <p style={{ fontSize: '14px' }}>Ask me anything and I'll help you with an answer.</p>
              </div>
            ) : (
              messages.map(msg => (
                <div
                  key={msg.id}
                  style={{
                    marginBottom: '16px',
                    display: 'flex',
                    justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start'
                  }}
                >
                  <div style={{
                    maxWidth: '70%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    background: msg.type === 'user' 
                      ? '#2ECC71' 
                      : isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
                    color: msg.type === 'user' ? 'white' : isDark ? '#E0E0E0' : '#333',
                    wordWrap: 'break-word',
                    fontSize: '14px'
                  }}>
                    {msg.content}
                    {msg.type === 'assistant' && <SpeechPlayback text={msg.content} language={language === 'hi' ? 'hi-IN' : 'en-IN'} />}
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column',
                gap: '8px', 
                marginLeft: '16px', 
                marginTop: '16px', 
                padding: '16px 20px', 
                borderRadius: '16px', 
                background: isDark ? 'rgba(46,204,113,0.15)' : 'rgba(46,204,113,0.08)', 
                border: `1px solid ${isDark ? 'rgba(46,204,113,0.3)' : 'rgba(46,204,113,0.2)'}`,
                maxWidth: 'max-content',
                animation: 'pulse 2s infinite ease-in-out'
              }}>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
                <span style={{ 
                  fontSize: '11px', 
                  fontWeight: 800, 
                  color: '#2ECC71', 
                  textTransform: 'uppercase', 
                  letterSpacing: '1px' 
                }}>
                  {t.thinking}
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={t.inputPlaceholder}
              style={{
                flex: 1,
                padding: '12px 16px',
                borderRadius: '8px',
                border: `1px solid ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)'}`,
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.02)',
                color: isDark ? '#E0E0E0' : '#333',
                fontSize: '14px'
              }}
              disabled={loading}
            />
            <VoiceInput label="Speak your question" disabled={loading} language={language === 'hi' ? 'hi-IN' : 'en-IN'} onTranscript={text => setInput(previous => previous ? `${previous} ${text}` : text)} />
            <button
              type="submit"
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                border: 'none',
                background: '#2ECC71',
                color: 'white',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: 600,
                transition: 'all 0.3s',
                opacity: loading ? 0.7 : 1
              }}
              disabled={loading}
            >
              <Send style={{ width: '18px', height: '18px' }} />
              {t.send}
            </button>
          </form>
        </GlassSection>
      </main>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .typing-dot {
          width: 10px;
          height: 10px;
          background-color: #2ECC71;
          border-radius: 50%;
          animation: typingBlink 1.4s infinite ease-in-out both;
        }
        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes typingBlink {
          0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
