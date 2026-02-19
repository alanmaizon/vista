# Homer (Microsoft Word Task Pane Add-in)

Homer is a minimal TypeScript baseline for a Word Task Pane add-in + backend API. It demonstrates:

- Summarize the current Word document
- Rewrite selected text (Simplify / Professional / Shorter)
- Add multiple pasted snippets and generate one unified summary

## Demo flow (3 steps)

1. Start both apps: `pnpm install && pnpm dev`
2. Sideload `apps/addin-word/manifest.xml` into Word and open the Homer task pane.
3. Use **Summarize Document** or **Rewrite Selection**, then insert/replace output in the document.

## Architecture

```text
+---------------------------+        HTTP         +-------------------------+
| Word Task Pane (React)    |  -----------------> | Express API (TypeScript)|
| - Office.js helpers       |                     | /api/summarize          |
| - Snippet inputs (MVP+)   | <-----------------  | /api/rewrite            |
+---------------------------+      JSON result    +-------------------------+
          |                                               |
          |                                               v
          |                                       +------------------+
          |                                       | LLMProvider      |
          |                                       | - MockProvider   |
          |                                       | - OpenAIProvider |
          |                                       +------------------+
          v
+---------------------------+
| Word document body/selection|
+---------------------------+
```

## Repo layout

```text
/
  apps/
    addin-word/
    backend/
  packages/
    shared/
```

## Local development

```bash
pnpm install
pnpm dev
```

Useful commands:

- `pnpm --filter @homer/backend dev`
- `pnpm --filter @homer/addin-word dev`
- `pnpm lint`
- `pnpm typecheck`

## Configuration

Copy `.env.example` to `.env` and adjust values.

- `BACKEND_PORT` defaults to `4000`
- `PROVIDER` defaults to `mock`
- `OPENAI_API_KEY` optional (required only when `PROVIDER=openai`)
- `MODEL` optional model name
- `VITE_BACKEND_URL` add-in API base URL

## Privacy-by-design

- Document text and snippet text are sent only when the user clicks summarize/rewrite.
- The backend does **not** log raw document/snippet text by default.
- Responses include a request ID for traceability without content logging.
- Mock provider is default for local demos with no external API calls.

## Roadmap

- Microsoft Graph multi-document ingestion (OneDrive/SharePoint)
- Foundry/Copilot Studio agent orchestration
- Citation mode with source grounding

## Next commits checklist

- [ ] Add integration tests for API validation and provider wiring
- [ ] Add taskpane UX polish (loading states per action, keyboard shortcuts)
- [ ] Add optional Bedrock provider implementation
- [ ] Add Office add-in command ribbon actions
