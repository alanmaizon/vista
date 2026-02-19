import type { RewriteMode, SummaryStyle } from "@homer/shared";
import type { LLMProvider } from "./LLMProvider.js";

const MODES: Record<RewriteMode, string> = {
  simplify: "Simplified",
  professional: "Professional",
  shorter: "Shorter"
};

function trimWords(value: string, maxWords = 60): string {
  const words = value.trim().split(/\s+/);
  return words.slice(0, maxWords).join(" ");
}

export class MockProvider implements LLMProvider {
  readonly name = "mock" as const;

  async summarize(input: {
    documents: { title: string; content: string }[];
    style: SummaryStyle;
    instructions?: string;
  }): Promise<string> {
    const lines = input.documents.map((doc, index) => {
      const head = trimWords(doc.content, input.style === "bullet" ? 20 : 35);
      if (input.style === "bullet") {
        return `- [${index + 1}] ${doc.title}: ${head}`;
      }
      return `${doc.title}: ${head}.`;
    });

    const instructionLine = input.instructions ? `\nInstructions noted: ${trimWords(input.instructions, 20)}.` : "";
    return input.style === "bullet" ? `${lines.join("\n")}${instructionLine}` : `${lines.join(" ")}${instructionLine}`;
  }

  async rewrite(input: { text: string; mode: RewriteMode; instructions?: string }): Promise<string> {
    const body = trimWords(input.text, input.mode === "shorter" ? 20 : 45);
    const prefix = MODES[input.mode];
    const suffix = input.instructions ? ` (${trimWords(input.instructions, 12)})` : "";
    return `${prefix}: ${body}${suffix}`;
  }
}
