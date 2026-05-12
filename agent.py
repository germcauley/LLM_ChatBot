import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"

import ollama as ollama_lib
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import date
import re
import ast
import operator
import subprocess
import tempfile
import PyPDF2
import wikipediaapi
from ddgs import DDGS
import json


@dataclass
class Tool:
    """A tool the agent can invoke."""
    name: str
    description: str
    parameters: dict          # JSON-schema-style param descriptions
    function: Callable        # The actual implementation

    def run(self, **kwargs) -> str:
        """Execute the tool safely, always returning a string."""
        try:
            result = self.function(**kwargs)
            return str(result)
        except Exception as e:
            return f"Error running {self.name}: {e}"

    def to_ollama_schema(self) -> dict:
        """Convert to the Ollama/OpenAI function-calling schema (used in Part B)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "required": list(self.parameters.keys()),
                    "properties": self.parameters,
                },
            },
        }


class ToolRegistry:
    """Holds all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def describe_for_prompt(self) -> str:
        """Generate the text description block the LLM sees (Part A)."""
        parts = []
        for tool in self._tools.values():
            params_str = json.dumps(tool.parameters, indent=2)
            parts.append(
                f"Tool: {tool.name}\n"
                f"Description: {tool.description}\n"
                f"Parameters: {params_str}"
            )
        return "\n\n".join(parts)

    def to_ollama_tools(self) -> list[dict]:
        """Generate the structured tool list for native calling (Part B)."""
        return [tool.to_ollama_schema() for tool in self._tools.values()]
    
# Whitelist of safe operations
_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
}

def _safe_eval(node):
    """Recursively evaluate an AST node using only whitelisted ops."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    else:
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    tree = ast.parse(expression.strip(), mode="eval")
    result = _safe_eval(tree)
    return f"{expression.strip()} = {result}"


calc_tool = Tool(
    name="calculator",
    description="Evaluate a mathematical expression. Supports +, -, *, /, **, %, //.",
    parameters={
        "expression": {"type": "string", "description": "A math expression, e.g. '(45 * 12) + 98'"},
    },
    function=calculator,
)

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of top results."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return f"No results found for: {query}"
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r['title']}\n    {r['body']}\n    Source: {r['href']}")
    return "\n\n".join(parts)


search_tool = Tool(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns titles, snippets, and URLs for the top results.",
    parameters={
        "query": {"type": "string", "description": "The search query."},
    },
    function=web_search,
)

print(search_tool.run(query="population of Ireland 2025"))


def wikipedia_lookup(topic: str) -> str:
    """Fetch the summary of a Wikipedia article."""
    wiki = wikipediaapi.Wikipedia(user_agent="AgentLab/1.0 (educational)", language="en")
    page = wiki.page(topic)
    if not page.exists():
        return f"Wikipedia article not found for: {topic}"
    return f"Wikipedia — {page.title}:\n{page.summary[:1500]}"


wiki_tool = Tool(
    name="wikipedia",
    description="Look up a topic on Wikipedia. Returns the article summary.",
    parameters={
        "topic": {"type": "string", "description": "The Wikipedia article title to look up."},
    },
    function=wikipedia_lookup,
)

print(wiki_tool.run(topic="Large language model")[:400])
