import { z } from "zod";

export const documentInputSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  content: z.string().min(1)
});

export const summarizeRequestSchema = z.object({
  documents: z.array(documentInputSchema).min(1),
  style: z.enum(["bullet", "paragraph"]),
  instructions: z.string().optional()
});

export const rewriteRequestSchema = z.object({
  text: z.string().min(1),
  mode: z.enum(["simplify", "professional", "shorter"]),
  instructions: z.string().optional()
});
