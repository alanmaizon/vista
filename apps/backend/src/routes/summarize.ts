import type { NextFunction, Request, Response, Router } from "express";
import { summarizeRequestSchema } from "@homer/shared";
import type { LLMProvider } from "../providers/LLMProvider.js";

export function mountSummarizeRoute(router: Router, provider: LLMProvider): void {
  router.post("/summarize", async (req: Request, res: Response, next: NextFunction) => {
    try {
      const input = summarizeRequestSchema.parse(req.body);
      const summary = await provider.summarize({
        documents: input.documents.map((doc) => ({ title: doc.title, content: doc.content })),
        style: input.style,
        instructions: input.instructions
      });

      res.json({
        summary,
        usage: {
          provider: provider.name,
          requestId: res.locals.requestId
        }
      });
    } catch (error) {
      next(error);
    }
  });
}
