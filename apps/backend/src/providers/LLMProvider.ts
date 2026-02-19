import type { RewriteMode, SummaryStyle } from "@homer/shared";

export interface LLMProvider {
  readonly name: "mock" | "openai" | "bedrock";
  summarize(input: {
    documents: { title: string; content: string }[];
    style: SummaryStyle;
    instructions?: string;
  }): Promise<string>;
  rewrite(input: {
    text: string;
    mode: RewriteMode;
    instructions?: string;
  }): Promise<string>;
}
