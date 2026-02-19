import { useMemo, useState } from "react";
import type {
  DocumentInput,
  RewriteMode,
  RewriteResponse,
  SummarizeResponse,
  SummaryStyle
} from "@homer/shared";
import {
  getDocumentText,
  getSelectionText,
  insertTextAtCursor,
  replaceSelection
} from "../office/word";
import "./app.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:4000";

type ResultState = { type: "summary" | "rewrite"; text: string } | null;

export default function App() {
  const [mode, setMode] = useState<RewriteMode>("simplify");
  const [style, setStyle] = useState<SummaryStyle>("bullet");
  const [instructions, setInstructions] = useState("");
  const [result, setResult] = useState<ResultState>(null);
  const [status, setStatus] = useState("Ready");
  const [snippets, setSnippets] = useState<DocumentInput[]>([]);
  const [snippetTitle, setSnippetTitle] = useState("");
  const [snippetContent, setSnippetContent] = useState("");

  const canAddSnippet = useMemo(
    () => snippetTitle.trim().length > 0 && snippetContent.trim().length > 0,
    [snippetContent, snippetTitle]
  );

  async function summarizeDocument(): Promise<void> {
    setStatus("Summarizing...");
    try {
      const docText = await getDocumentText();
      if (!docText && snippets.length === 0) {
        setStatus("No document text or snippets found.");
        return;
      }

      const documents: DocumentInput[] = [
        ...(docText ? [{ id: "doc", title: "Current Word document", content: docText }] : []),
        ...snippets
      ];

      const response = await fetch(`${BACKEND_URL}/api/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documents,
          style,
          instructions: instructions.trim() || undefined
        })
      });

      if (!response.ok) {
        throw new Error("Summarize request failed");
      }

      const payload = (await response.json()) as SummarizeResponse;
      setResult({ type: "summary", text: payload.summary });
      setStatus(`Summary ready (${payload.usage.provider})`);
    } catch {
      setStatus("Unable to summarize. Make sure Word + backend are running.");
    }
  }

  async function rewriteSelection(): Promise<void> {
    setStatus("Rewriting...");
    try {
      const selected = await getSelectionText();
      if (!selected) {
        setStatus("Please select a paragraph in Word first.");
        return;
      }

      const response = await fetch(`${BACKEND_URL}/api/rewrite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: selected,
          mode,
          instructions: instructions.trim() || undefined
        })
      });

      if (!response.ok) {
        throw new Error("Rewrite request failed");
      }

      const payload = (await response.json()) as RewriteResponse;
      setResult({ type: "rewrite", text: payload.rewritten });
      setStatus(`Rewrite ready (${payload.usage.provider})`);
    } catch {
      setStatus("Unable to rewrite. Make sure Word + backend are running.");
    }
  }

  function addSnippet(): void {
    if (!canAddSnippet) return;
    setSnippets((current) => [
      ...current,
      {
        id: `snippet-${current.length + 1}`,
        title: snippetTitle.trim(),
        content: snippetContent.trim()
      }
    ]);
    setSnippetTitle("");
    setSnippetContent("");
  }

  return (
    <main className="container">
      <h1>Homer</h1>
      <p className="hint">Summarize or rewrite directly from Word.</p>

      <div className="card">
        <label>
          Rewrite mode
          <select value={mode} onChange={(event) => setMode(event.target.value as RewriteMode)}>
            <option value="simplify">Simplify</option>
            <option value="professional">Professional</option>
            <option value="shorter">Shorter</option>
          </select>
        </label>

        <label>
          Summary style
          <select value={style} onChange={(event) => setStyle(event.target.value as SummaryStyle)}>
            <option value="bullet">Bullet</option>
            <option value="paragraph">Paragraph</option>
          </select>
        </label>

        <label>
          Extra context / instructions
          <textarea
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            rows={3}
            placeholder="Optional"
          />
        </label>

        <div className="buttonRow">
          <button onClick={summarizeDocument}>Summarize Document</button>
          <button onClick={rewriteSelection}>Rewrite Selection</button>
        </div>
      </div>

      <div className="card">
        <h2>Document snippets (MVP+)</h2>
        <input
          placeholder="Snippet title"
          value={snippetTitle}
          onChange={(event) => setSnippetTitle(event.target.value)}
        />
        <textarea
          placeholder="Paste snippet content"
          value={snippetContent}
          onChange={(event) => setSnippetContent(event.target.value)}
          rows={3}
        />
        <button onClick={addSnippet} disabled={!canAddSnippet}>
          Add snippet
        </button>
        <ul>
          {snippets.map((snippet) => (
            <li key={snippet.id}>{snippet.title}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h2>Result</h2>
        <pre>{result?.text || "No result yet."}</pre>
        <div className="buttonRow">
          <button
            onClick={() => result && insertTextAtCursor(result.text)}
            disabled={!result}
          >
            Insert into document
          </button>
          <button
            onClick={() => result && replaceSelection(result.text)}
            disabled={!result || result.type !== "rewrite"}
          >
            Replace selection
          </button>
        </div>
      </div>

      <p className="status">{status}</p>
      <p className="privacy">Privacy: content is sent only on action; backend avoids raw text logs.</p>
    </main>
  );
}
