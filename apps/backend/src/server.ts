import dotenv from "dotenv";
import cors from "cors";
import express from "express";
import rateLimit from "express-rate-limit";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { errorHandler, notFound } from "./middleware/errorHandler.js";
import { requestId } from "./middleware/requestId.js";
import { createProvider } from "./providers/index.js";
import { mountRewriteRoute } from "./routes/rewrite.js";
import { mountSummarizeRoute } from "./routes/summarize.js";

const app = express();
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
dotenv.config({ path: resolve(__dirname, "../../../.env") });
dotenv.config();
const port = Number(process.env.BACKEND_PORT || 4000);
const provider = createProvider();

app.use(requestId);
app.use(
  cors({
    origin(origin, callback) {
      if (!origin || /^https?:\/\/localhost(:\d+)?$/.test(origin)) {
        callback(null, true);
        return;
      }
      callback(new Error("Origin not allowed"));
    }
  })
);
app.use(express.json({ limit: "1mb" }));
app.use(
  rateLimit({
    windowMs: 60_000,
    max: 30,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: "Too many requests. Try again shortly." }
  })
);

const api = express.Router();
mountSummarizeRoute(api, provider);
mountRewriteRoute(api, provider);

app.get("/health", (_req, res) => {
  res.json({ ok: true, provider: provider.name });
});
app.use("/api", api);
app.use(notFound);
app.use(errorHandler);

app.listen(port, () => {
  console.log(`Homer backend listening on http://localhost:${port}`);
});
