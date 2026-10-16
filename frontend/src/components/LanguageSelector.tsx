import { useLanguage } from '@/contexts/LanguageContext';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Globe } from 'lucide-react';

import { APP_LANGUAGES } from '@/lib/languagePreference';
const languages = APP_LANGUAGES.map(([code, label]) => ({code, label}));

export function LanguageSelector() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="notranslate" translate="no">
      <Select value={language} onValueChange={(v) => setLanguage(v as any)}>
        <SelectTrigger className="w-[115px] bg-card border-border">
          <Globe className="w-4 h-4 mr-2 text-muted-foreground" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-card border-border">
          {languages.map((lang) => (
            <SelectItem key={lang.code} value={lang.code}>
              {lang.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
