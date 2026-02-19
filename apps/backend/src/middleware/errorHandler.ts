import type { NextFunction, Request, Response } from "express";
import { ZodError } from "zod";

export function notFound(_req: Request, res: Response): void {
  res.status(404).json({ error: "Not Found" });
}

export function errorHandler(err: unknown, req: Request, res: Response, _next: NextFunction): void {
  const message = err instanceof Error ? err.message : "Unexpected server error";
  const status = err instanceof ZodError ? 400 : 500;
  res.status(status).json({ error: message, requestId: res.locals.requestId });
}
