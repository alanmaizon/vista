import type { LLMProvider } from "./LLMProvider.js";
import { MockProvider } from "./MockProvider.js";
import { OpenAIProvider } from "./OpenAIProvider.js";

export function createProvider(): LLMProvider {
  const providerName = process.env.PROVIDER?.toLowerCase() ?? "mock";

  if (providerName === "openai") {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error("OPENAI_API_KEY is required when PROVIDER=openai");
    }
    return new OpenAIProvider(process.env.OPENAI_API_KEY, process.env.MODEL || "gpt-4o-mini");
  }

  return new MockProvider();
}
