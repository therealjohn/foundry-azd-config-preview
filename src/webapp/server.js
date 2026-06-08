// Copyright (c) Microsoft Corporation. All rights reserved.
//
// Customer support chat UI. Calls the triage agent to route, then talks to
// the chosen specialist agent. Demonstrates a non-Foundry service
// (host: containerapp) that consumes the Foundry agents declared in the
// same azure.yaml.

import express from "express";
import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PROJECT_ENDPOINT = mustGetenv("FOUNDRY_PROJECT_ENDPOINT");
const TRIAGE_AGENT = process.env.TRIAGE_AGENT_NAME ?? "triage-agent";
const SUPPORT_AGENT = process.env.SUPPORT_AGENT_NAME ?? "support-agent";
const RESEARCH_AGENT = process.env.RESEARCH_AGENT_NAME ?? "research-agent";

const credential = new DefaultAzureCredential();
const getToken = getBearerTokenProvider(credential, "https://ai.azure.com/.default");

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

app.post("/api/chat", async (req, res) => {
  try {
    const message = String(req.body?.message ?? "").trim();
    if (!message) return res.status(400).json({ error: "message required" });

    // TODO: wire the actual responses-protocol call here.
    // Pseudo-code:
    //   const route = await invokeAgent(TRIAGE_AGENT, { input: message });
    //   const target = route.route ?? SUPPORT_AGENT;
    //   const answer = await invokeAgent(target, { input: message });
    //   return res.json({ route: target, reply: answer });

    res.json({
      route: SUPPORT_AGENT,
      reply: `[stub] ${SUPPORT_AGENT} would answer: ${message}`,
    });
  } catch (err) {
    console.error("chat error", err);
    res.status(500).json({ error: "internal error" });
  }
});

app.get("/api/health", (_req, res) => res.json({ status: "ok" }));

async function invokeAgent(agentName, payload) {
  // TODO: implement Foundry responses-protocol HTTP client. The agent
  // endpoint is derived from PROJECT_ENDPOINT and the agent name.
  const token = await getToken();
  void token;
  void agentName;
  void payload;
  throw new Error("invokeAgent: not implemented in this sample");
}

function mustGetenv(name) {
  const v = process.env[name];
  if (!v) throw new Error(`${name} is not set`);
  return v;
}

const port = Number(process.env.PORT ?? 8080);
app.listen(port, () => {
  console.log(`webapp listening on http://0.0.0.0:${port}`);
  console.log(`project endpoint: ${PROJECT_ENDPOINT}`);
});
