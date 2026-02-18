"""
Multi-Agent System - Local Claude AI Version (Anthropic SDK)
=============================================================
Functionally identical to the Azure version but uses the Anthropic
Python SDK instead of Semantic Kernel + Azure OpenAI.

Agents take turns in a round-robin loop managed by this script.
The loop ends when:
  • The Product Owner says "READY FOR USER APPROVAL", then
  • The user types "APPROVED"

On APPROVED:
  1. The latest ```html ... ``` block is extracted from the history
  2. Saved to index.html
  3. push_to_github.sh is generated and executed

Requirements: pip install anthropic python-dotenv
"""

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Literal

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = 4096
MAX_ROUNDS = 20          # safety cap on agentic loops

# ---------------------------------------------------------------------------
# Persona definitions  (identical wording to Azure version)
# ---------------------------------------------------------------------------

PERSONAS = {
    "BusinessAnalyst": {
        "system": (
            "You are a Business Analyst which will take the requirements from the user "
            "(also known as a 'customer') and create a project plan for creating the "
            "requested app. The Business Analyst understands the user requirements and "
            "creates detailed documents with requirements and costing. The documents "
            "should be usable by the SoftwareEngineer as a reference for implementing "
            "the required features, and by the Product Owner for reference to determine "
            "if the application delivered by the Software Engineer meets all of the "
            "user's requirements."
        ),
    },
    "SoftwareEngineer": {
        "system": (
            "You are a Software Engineer, and your goal is create a web app using HTML "
            "and JavaScript by taking into consideration all the requirements given by "
            "the Business Analyst. The application should implement all the requested "
            "features. Deliver the code to the Product Owner for review when completed. "
            "You can also ask questions of the BusinessAnalyst to clarify any "
            "requirements that are unclear."
        ),
    },
    "ProductOwner": {
        "system": (
            "You are the Product Owner which will review the software engineer's code to "
            "ensure all user requirements are completed. You are the guardian of quality, "
            "ensuring the final product meets all specifications. IMPORTANT: Verify that "
            "the Software Engineer has shared the HTML code using the format "
            "```html [code] ```. This format is required for the code to be saved and "
            "pushed to GitHub. Once all client requirements are completed and the code is "
            "properly formatted, reply with 'READY FOR USER APPROVAL'. If there are "
            "missing features or formatting issues, you will need to send a request back "
            "to the SoftwareEngineer or BusinessAnalyst with details of the defect."
        ),
    },
}

AGENT_ORDER: List[str] = ["BusinessAnalyst", "SoftwareEngineer", "ProductOwner"]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Message:
    role: Literal["user", "assistant"]
    name: str          # agent name or "User"
    content: str


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

class ClaudeAgent:
    """Wraps a single Claude API call for one persona."""

    def __init__(self, name: str, client: anthropic.Anthropic):
        self.name = name
        self.system = PERSONAS[name]["system"]
        self.client = client

    def respond(self, history: List[Message]) -> str:
        """Build a prompt from shared history and get a response."""
        # Claude messages must alternate user/assistant.
        # We flatten the multi-agent history into a single conversation
        # by prepending speaker labels to each message.
        messages = []
        for msg in history:
            label = f"[{msg.name}]: " if msg.name != "User" else "[User]: "
            messages.append({"role": msg.role, "content": label + msg.content})

        # Ensure the last message is from the user role (Claude requirement)
        if messages and messages[-1]["role"] == "assistant":
            messages.append({
                "role": "user",
                "content": f"[System]: Please continue as {self.name}.",
            })

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=self.system,
            messages=messages,
        )
        return response.content[0].text


# ---------------------------------------------------------------------------
# HTML & GitHub helpers  (identical logic to Azure version)
# ---------------------------------------------------------------------------

def extract_html(history: List[Message]) -> str | None:
    pattern = re.compile(r"```html\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    for msg in reversed(history):
        match = pattern.search(msg.content)
        if match:
            return match.group(1).strip()
    return None


def save_html(html_content: str, filepath: str = "index.html") -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[✓] HTML saved to {filepath}")


def push_to_github() -> None:
    """
    Push index.html to GitHub using native git commands.
    Works on Windows, macOS, and Linux without requiring bash.
    """
    branch = os.getenv("GITHUB_BRANCH", "main")

    def run(cmd: list[str], label: str) -> bool:
        print(f"[→] {label} …")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.returncode != 0:
            # git commit exits 1 when there's nothing new to commit — that's OK
            if "nothing to commit" in result.stdout + result.stderr:
                print("[!] Nothing new to commit — index.html unchanged.")
                return True
            print(f"[✗] Failed: {result.stderr.strip()}")
            return False
        return True

    print("\n[→] Pushing to GitHub …")
    ok = (
        run(["git", "add", "index.html"],                                    "Staging index.html")
        and run(["git", "commit", "-m", "Auto-push approved app [multi-agent]"], "Committing")
        and run(["git", "push", "origin", branch],                           f"Pushing to {branch}")
    )

    if ok:
        print("[✓] GitHub push succeeded.")
    else:
        print("[!] Push encountered an issue. Try manually:")
        print("      git add index.html")
        print("      git commit -m 'update'")
        print(f"     git push origin {branch}")


# ---------------------------------------------------------------------------
# Termination check
# ---------------------------------------------------------------------------

def should_terminate(history: List[Message]) -> bool:
    """Return True when the latest user message is 'APPROVED'."""
    for msg in reversed(history):
        if msg.name == "User":
            return msg.content.strip().upper() == "APPROVED"
    return False


def product_owner_ready(history: List[Message]) -> bool:
    """Return True when the Product Owner has said READY FOR USER APPROVAL."""
    for msg in reversed(history):
        if msg.name == "ProductOwner":
            return "READY FOR USER APPROVAL" in msg.content.upper()
    return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_multi_agent_chat(user_request: str) -> None:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    agents = {name: ClaudeAgent(name, client) for name in AGENT_ORDER}

    history: List[Message] = [
        Message(role="user", name="User", content=user_request)
    ]

    print(f"\n{'='*70}")
    print("Multi-Agent Conversation Started  |  Claude AI (local)")
    print(f"{'='*70}")
    print(f"\n[User]: {user_request}\n")

    round_idx = 0
    agent_idx = 0
    waiting_for_approval = False

    while round_idx < MAX_ROUNDS:
        if waiting_for_approval:
            # Prompt the human user
            user_input = input("\nType 'APPROVED' to push to GitHub, or provide feedback: ").strip()
            history.append(Message(role="user", name="User", content=user_input))

            if should_terminate(history):
                print("\n[✓] APPROVED received. Running post-approval steps …\n")
                html = extract_html(history)
                if html:
                    save_html(html)
                    push_to_github()
                else:
                    print("[!] No HTML code block found. Skipping push.")
                break
            else:
                # Re-enter agent loop from Product Owner
                waiting_for_approval = False
                agent_idx = AGENT_ORDER.index("ProductOwner")

        # Pick the next agent in rotation
        name = AGENT_ORDER[agent_idx % len(AGENT_ORDER)]
        agent = agents[name]

        print(f"# assistant - {name} (thinking…)")
        response = agent.respond(history)

        print(f"# assistant - {name}:\n{response}\n")
        print("-" * 60)

        history.append(Message(role="assistant", name=name, content=response))

        # Check if Product Owner is satisfied
        if name == "ProductOwner" and product_owner_ready(history):
            waiting_for_approval = True
            print("\n[ProductOwner] → Code is ready for user approval.\n")
            continue

        agent_idx += 1
        round_idx += 1

    else:
        print("\n[!] Maximum rounds reached without approval.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def interactive_session() -> None:
    print("=" * 70)
    print("  Multi-Agent System  |  Local Claude AI (Anthropic SDK)")
    print("=" * 70)

    user_input = input("\nEnter your app request: ").strip()
    if not user_input:
        user_input = "Build a calculator app with basic arithmetic operations."

    await run_multi_agent_chat(user_input)


if __name__ == "__main__":
    asyncio.run(interactive_session())
