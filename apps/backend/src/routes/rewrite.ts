import type { NextFunction, Request, Response, Router } from "express";
import { rewriteRequestSchema } from "@homer/shared";
import type { LLMProvider } from "../providers/LLMProvider.js";

export function mountRewriteRoute(router: Router, provider: LLMProvider): void {
  router.post("/rewrite", async (req: Request, res: Response, next: NextFunction) => {
    try {
      const input = rewriteRequestSchema.parse(req.body);
      const rewritten = await provider.rewrite({
        text: input.text,
        mode: input.mode,
        instructions: input.instructions
      });

      res.json({
        rewritten,
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
