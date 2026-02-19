import type { RewriteMode, SummaryStyle } from "@homer/shared";
import type { LLMProvider } from "./LLMProvider.js";

export class OpenAIProvider implements LLMProvider {
  readonly name = "openai" as const;

  constructor(
    private readonly apiKey: string,
    private readonly model: string
  ) {}

  private async callOpenAI(prompt: string): Promise<string> {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`
      },
      body: JSON.stringify({
        model: this.model,
        messages: [{ role: "user", content: prompt }],
        temperature: 0.2
      })
    });

    if (!response.ok) {
      throw new Error(`OpenAI request failed with status ${response.status}`);
    }

    const payload = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };

    return payload.choices?.[0]?.message?.content?.trim() || "";
  }

  async summarize(input: {
    documents: { title: string; content: string }[];
    style: SummaryStyle;
    instructions?: string;
  }): Promise<string> {
    const docs = input.documents
      .map((doc) => `Title: ${doc.title}\nContent:\n${doc.content}`)
      .join("\n\n");
    const prompt = `Summarize the following documents in ${input.style} style. ${input.instructions ?? ""}\n\n${docs}`;
    return this.callOpenAI(prompt);
  }

  async rewrite(input: {
    text: string;
    mode: RewriteMode;
    instructions?: string;
  }): Promise<string> {
    const prompt = `Rewrite the text in ${input.mode} mode. ${input.instructions ?? ""}\n\n${input.text}`;
    return this.callOpenAI(prompt);
  }
}
