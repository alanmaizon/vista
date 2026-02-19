export type SummaryStyle = "bullet" | "paragraph";
export type RewriteMode = "simplify" | "professional" | "shorter";

export interface DocumentInput {
  id: string;
  title: string;
  content: string;
}

export interface SummarizeRequest {
  documents: DocumentInput[];
  style: SummaryStyle;
  instructions?: string;
}

export interface UsageInfo {
  provider: "mock" | "openai" | "bedrock";
  requestId: string;
}

export interface SummarizeResponse {
  summary: string;
  usage: UsageInfo;
}

export interface RewriteRequest {
  text: string;
  mode: RewriteMode;
  instructions?: string;
}

export interface RewriteResponse {
  rewritten: string;
  usage: UsageInfo;
}
