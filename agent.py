import os
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
import ollama as ollama_lib
from dataclasses import dataclass
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


def python_exec(code: str) -> str:
    """Execute a Python code snippet and return stdout/stderr."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                ["python3", f.name],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                output += f"\nSTDERR: {result.stderr.strip()}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Code execution timed out (10s limit)."
        finally:
            os.unlink(f.name)


python_tool = Tool(
    name="python_exec",
    description="Execute a Python code snippet. Use for data processing or computation that doesn't fit the calculator. Use print() for output.",
    parameters={
        "code": {"type": "string", "description": "Python code to execute. Use print() for output."},
    },
    function=python_exec,
)


def read_pdf(file_path: str) -> str:
    try:
        result=[]
        # Open the PDF using PyPDF2.PdfReader
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            # Loop through all pages and extract text from each
            for i in reader.pages:
                result.append(i.extract_text())
        # Return all the text joined together as a string
        return "\n".join(result)
    except FileNotFoundError:
            return f"Error: File not found at {file_path}"

#  define the tool like the ones we alrady used
pdf_reader_tool = Tool(
    name="pdf_reader",
    description="Parse text from pdf files",
    parameters={
        "file_path": {"type": "string", "description": "The filepath of the pdf file you want to read"},
    },
    function=read_pdf,
)


today = date.today().isoformat()
class NativeToolAgent:
    """Agent using Qwen3's native function-calling via Ollama's chat API."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        registry: ToolRegistry = None,
        max_iterations: int = 8,
        enable_thinking: bool = True,
        verbose: bool = True,
        memories: list = None
    ):
        self.model = model
        self.registry = registry
        self.max_iterations = max_iterations
        self.enable_thinking = enable_thinking
        self.verbose = verbose
        # add memory
        memory_text = ""
        if memories:
            memory_text = "\n\nThe following facts have been shared by the user you are talking to. Use them when relevant but do not introduce yourself using them:\n" + "\n".join(f"- {m}" for m in memories)

        self.messages = [
            {"role": "system", "content": (
                f"You are a helpful assistant with tool access. Today's date is {today}. "
                "Use tools when needed to answer accurately. "
                "Do not guess — look things up. "
                "Answer only the specific question asked. If the user asks about one memory, answer that one thing only, do not list other memories. "
                "NEVER use emojis in your response. "
                f"{memory_text}"
            )}
        ]

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def reset(self):
        """Reset conversation history"""
        self.messages = self.messages[:1]
        self._log("Conversation history has been reset.")

    def check_context_length(self):
        """Summarise the conversation history if it gets too long."""
        # if there are more than 20 messages, summarise the chat history
        if len(self.messages) > 20:
            
            summary_response = ollama_lib.chat(
                model=self.model,
                messages=self.messages + [
                    {"role": "user", "content": "Summarise our conversation so far in a few sentences."}
                ],
            )
            summary = summary_response.message.content
            
            # Replace history with system message + summary
            self.messages = [
                self.messages[0],  # keep system message so agent retains instructions etc
                {"role": "assistant", "content": f"Previous conversation summary: {summary}"}
            ]
            self._log(" Context summarised.")

    def run(self, query: str) -> tuple[str, list[dict]]:
        """Execute the agent loop using native tool calling."""
        # always check converation length, summarise if it reaches limit we set
        self.check_context_length()
        # appends to existing chat history instead of a fresh conversation each time
        # we want to take in more tha just plain text so use re to extract
        match = re.search(r'\[IMAGE_DATA:(.*?)\]', query)
        if match:
            image_data = match.group(1)
            clean_message = re.sub(r'\[IMAGE_DATA:.*?\]', '', query).strip()
            self.messages.append({
                "role": "user", 
                "content": clean_message,
                "images": [image_data]
            })
        else:
            self.messages.append({"role": "user", "content": query})
        
        tools = self.registry.to_ollama_tools()
        trace = []

        for i in range(1, self.max_iterations + 1):
            self._log(f"\n{'='*60}\n  ITERATION {i}\n{'='*60}")

            response = ollama_lib.chat(
                model=self.model,
                messages=self.messages,
                tools=tools,
                think=self.enable_thinking,
                options={"temperature": 0.1},
            )
            msg = response.message

            # No tool calls → final answer
            if not msg.tool_calls:
                self._log(f"\n✅ Final Answer: {msg.content[:300]}")
                trace.append({"iteration": i, "type": "answer", "content": msg.content})
                return msg.content, trace

            # Process tool calls
            self.messages.append(msg)

            for call in msg.tool_calls:
                fn_name = call.function.name
                fn_args = call.function.arguments
                self._log(f"\n🔧 Tool call: {fn_name}({fn_args})")

                tool = self.registry.get(fn_name)
                if tool is None:
                    result = f"Error: Unknown tool '{fn_name}'"
                else:
                    result = tool.run(**fn_args)

                if len(result) > 2000:
                    result = result[:2000] + "\n... (truncated)"

                self._log(f"  👁️ Result: {result[:200]}")

                self.messages.append({
                    "role": "tool",
                    "tool_name": fn_name,
                    "content": result,
                })
                trace.append({
                    "iteration": i, "type": "tool_call",
                    "tool": fn_name, "args": fn_args,
                    "result": result[:500],
                })

        self._log(f"\n Max iterations ({self.max_iterations}) reached.")
        return "Reached step limit without a final answer.", trace
    # agent with memory parameter
def create_agent(model: str = "qwen3:8b",memories: list = None) -> NativeToolAgent:
    """Create and return a configured agent with all tools registered."""
    registry = ToolRegistry()
    registry.register(calc_tool)
    registry.register(search_tool)
    registry.register(wiki_tool)
    registry.register(python_tool)
    registry.register(pdf_reader_tool)
    
    return NativeToolAgent(model=model, registry=registry, memories=memories)