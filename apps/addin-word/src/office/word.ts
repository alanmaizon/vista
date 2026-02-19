/* global Word */

declare global {
  interface Window {
    Word?: typeof Word;
  }
}

function ensureWordApi(): void {
  if (!window.Word) {
    throw new Error("Word API unavailable. Open this app inside Microsoft Word.");
  }
}

export async function getDocumentText(): Promise<string> {
  ensureWordApi();
  return window.Word!.run(async (context) => {
    const body = context.document.body;
    body.load("text");
    await context.sync();
    return body.text?.trim() ?? "";
  });
}

export async function getSelectionText(): Promise<string> {
  ensureWordApi();
  return window.Word!.run(async (context) => {
    const selection = context.document.getSelection();
    selection.load("text");
    await context.sync();
    return selection.text?.trim() ?? "";
  });
}

export async function insertTextAtCursor(text: string): Promise<void> {
  ensureWordApi();
  await window.Word!.run(async (context) => {
    const selection = context.document.getSelection();
    selection.insertText(text, "End");
    await context.sync();
  });
}

export async function replaceSelection(text: string): Promise<void> {
  ensureWordApi();
  await window.Word!.run(async (context) => {
    const selection = context.document.getSelection();
    selection.insertText(text, "Replace");
    await context.sync();
  });
}
