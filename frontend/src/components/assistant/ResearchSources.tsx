import { ExternalLink } from "lucide-react";
export interface ResearchResult { preparation?: {language?: string; requested_language?: string; translation_status?: string}; available?: boolean; answer?: string; status?: string; retrieved_at?: string; sources?: { id: number; title: string; url: string }[]; search_suggestions_html?: string }
export function ResearchSources({ result }: { result: ResearchResult }) {
  const sources = (result.sources || []).filter(source => /^https?:\/\//i.test(source.url));
  if (!result.available) return <p className="saathi-prepared-note">Web research is unavailable right now. Your saved farm records are still available.</p>;
  return <details className="saathi-research"><summary>Research & sources · {sources.length}</summary>
    {result.answer && <p style={{whiteSpace: "pre-wrap"}}>{result.answer}</p>}
    <ul>{sources.map((source, index) => <li key={`${source.id}:${index}`}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<ExternalLink size={12}/></a></li>)}</ul>
    {result.retrieved_at && <small>Checked {new Date(result.retrieved_at).toLocaleString()}</small>}
    {result.search_suggestions_html && <iframe title="Google Search suggestions" sandbox="allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" srcDoc={result.search_suggestions_html} style={{border: 0, width: "100%", height: 100}}/>}
  </details>;
}
