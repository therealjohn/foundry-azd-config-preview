# Copyright (c) Microsoft. All rights reserved.
#
# Support agent -- handles general customer support questions.
# Deploy mode: code-deploy (runtime: stack: python in azure.yaml). No
# Dockerfile required. Foundry schedules this on a managed Python base image.

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()


SYSTEM_PROMPT = """You are a friendly customer support specialist for our
product. Answer questions concisely. When a question requires deep research
across the web or external systems, defer to the research-agent instead of
guessing. Cite documentation links when available.
"""


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    # Toolbox tools (web_search, code_interpreter, file_search) are attached
    # by Foundry server-side from the support-toolbox entry referenced in
    # azure.yaml's foundry.agents.support-agent.toolboxes list. We do not
    # construct them locally.
    # TODO: wire any agent-side state (memory, output processors) here.

    agent = Agent(
        client=client,
        instructions=SYSTEM_PROMPT,
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
