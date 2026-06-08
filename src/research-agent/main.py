# Copyright (c) Microsoft. All rights reserved.
#
# Research agent -- deep research using web search, MCP tools, and Azure
# AI Search RAG.
#
# Deploy mode: container (docker: in azure.yaml). The Dockerfile in this
# directory is used to build the image; remoteBuild: true means ACR builds
# it on push.

import asyncio
import logging
import os
from collections.abc import Callable

import httpx
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a research specialist for a customer support
platform. Your job is to answer questions that require digging across the
web, code repositories, or our internal knowledge base. Always cite your
sources. Be concise -- a busy support agent is reading your output.
"""


def _resolve_toolbox_endpoint() -> str:
    """Construct the toolbox MCP endpoint from Foundry env vars.

    The Foundry hosting scaffolding injects FOUNDRY_PROJECT_ENDPOINT.
    TOOLBOX_NAME comes from foundry.agents.research-agent.env in azure.yaml
    -- or you can override with FOUNDRY_TOOLBOX_ENDPOINT for local dev.
    """
    if (override := os.environ.get("FOUNDRY_TOOLBOX_ENDPOINT")):
        return override
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    toolbox_name = os.environ.get("TOOLBOX_NAME", "research-toolbox")
    return f"{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1"


class _ToolboxAuth(httpx.Auth):
    """Injects a fresh bearer token on every request."""

    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._get_token = token_provider

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request


async def main():
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

    toolbox_endpoint = _resolve_toolbox_endpoint()
    toolbox_name = os.environ.get("TOOLBOX_NAME") or toolbox_endpoint.rsplit("/mcp", 1)[0].rsplit("/", 1)[-1]

    async with httpx.AsyncClient(
        auth=_ToolboxAuth(token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    ) as http_client:
        toolbox = MCPStreamableHTTPTool(
            name=toolbox_name,
            url=toolbox_endpoint,
            http_client=http_client,
            load_prompts=False,
        )

        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        )

        agent = Agent(
            client=client,
            instructions=SYSTEM_PROMPT,
            tools=toolbox,
            default_options={"store": False},
        )

        server = ResponsesHostServer(agent)
        await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
