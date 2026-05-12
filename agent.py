import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"

import ollama as ollama_lib
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import date
import json
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

print(calc_tool.run(expression="(15 ** 2) + (20 ** 2)"))