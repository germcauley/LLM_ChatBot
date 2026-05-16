# Technical Report  AI Chat Assistant
**CT5227 AI Model Deployment | Assignment 3**
**Student:** Gerald McAuley | **Student ID:** 25105693



## 1. Introduction

This report describes the design, implementation, and deployment of an AI Chat Assistant built for Assignment 3 of CT5227 AI Model Deployment. The application is a browser based chat interface that wraps an LLM powered agent capable of answering questions, searching the web, performing calculations, wriying and executing Python code, looking up Wikipedia, reading PDF files, and processing uploaded images(depending on model used). The system runs entirely inside a Docker container and communicates with a locally hosted LLM via Ollama.

The goal was to apply the deployment concepts covered in previous labs, Docker for containerisation, and agent design in a single, self contained, working application.


## 2. System Architecture

The application has the following architecture:

```
Browser (HTML/JS)
      │  HTTP POST /chat
      ▼
Flask Web Application (app.py)
      │  calls agent.run(message)
      ▼
NativeToolAgent (agent.py)
      │  ollama.chat() with tool definitions
      ▼
Ollama (host machine, port 11434)
      │  runs qwen3:8b model
      ▼
Tool Implementations (calculator, web_search, wikipedia, python_exec, pdf_reader)
```

The Flask app handles all HTTP requests: routing, file uploads, memory saving, and history logging. The agent layer handles all AI reasoning and tool orchestration. The Ollama process runs on the host machine outside the container the container reaches it via the  DNS name `host.docker.internal`.



## 3. Flask Web Application

### 3.1 Why Flask

Flask was chosen because it is lightweight, requires minimal boilerplate, and gives full control over routing and request handling. 

### 3.2 Routes

The application has three routes:

| Route | Method | Purpose |
|-|--|-|
| `/` | GET | Serves the chat UI (renders `index.html`) |
| `/chat` | POST | Receives user message and/or file, runs the agent, returns the reply as JSON |
| `/reset` | POST | Resets the agent's conversation history |

### 3.3 Request Flow

When a user submits a message, the `/chat` route:
1. Reads the text message and any uploaded file from the request
2. If the message starts with `"remember "`, it saves the text to the user's JSON config file and returns immediately no agent call needed
3. If a PDF was uploaded, it is saved to a temporary file, parsed with `read_pdf()`, and the extracted text is appended to the message before passing to the agent
4. If an image was uploaded, it is base64-encoded and embedded in the message string using a `[IMAGE_DATA:...]` tag that the agent knows how to extract, image processing requires a model. Due to time constraints I did not test this feature as it required a vision capable model.
5. The message is passed to `agent.run()`, which returns a reply and a trace
6. The full message (timestamp, user ID, prompt, reply, tool call trace) is appended to a JSON history file
7. The reply is returned as `jsonify({"reply": answer})`

### 3.4 Startup

Two functions run at module load time before Flask starts serving requests:

- `load_or_create_files()`  creates the `user_config/` directory and user JSON file if they do not exist, and creates an empty history file
- `load_memories()`  reads any saved memories from the user config and passes them to `create_agent()` so the agent's system prompt includes them from the first message

This means persistent user data from previous sessions is available immediately when the app starts.

### 3.5 Front-End UI

The chat interface is a single HTML file (`templates/index.html`) with no external CSS framework. The design uses a retro terminal aesthetic: black background (`#000`), green text (`#00ff41`) with the **Press Start 2P** pixel font loaded from Google Fonts. User messages are displayed in white (`#ffffff`) to distinguish them from bot replies in green.

The layout consists of a scrollable chat history box and an input row containing a file attachment button (clip icon SVG), a growing `<textarea>` for user input of varying length, and Send/Reset buttons. All button and input borders use the same colour scheme. The `marked.js` library (loaded from CDN) parses markdown in bot responses so code blocks, bold text, and lists render correctly.

The send flow is handled with `fetch()` to the `/chat` endpoint  the page never reloads. A "Bot: thinking..." placeholder is injected immediately and removed when the response arrives, giving the user visual feedback during inference. The `<textarea>` auto grows with content and submits on Enter (Shift+Enter for newlines). Pixel icons from Streamline HQ (SVG format, served via Flask's `/static/` route) provide the attachment clip and header computer graphics.



## 4. Agent Design

### 4.1 From Lab to Assignment

The agent is based on the NativeToolAgent developed in Week 10 Lab. That lab introduced Ollama's native function calling interface as a more reliable alternative to the manual ReAct loop from Part A. In Part A, the model's raw text output had to be parsed with regex to extract the tool name and input:

```
thought_match = re.search(
        r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:))", text, re.DOTALL
    )
```

The native approach removes the need for this verbose approach entirely. Ollama returns a structured object that is accessed directly:
```
for call in msg.tool_calls:
    fn_name = call.function.name
    fn_args = call.function.arguments
```
The assignment then extended this agent with: persistent conversation history, context summarisation, a user memory system, pdf file input, and integration into a Flask web application.


### 4.2 Model Choice

The model used is **qwen3:8b** running via **Ollama**. This has several benefits:
- It provides a clean Python client (`ollama` library) with native tool calling support
- No separate inference server setup is needed  one command (`ollama pull qwen3:8b`) is all that is required

The `OLLAMA_HOST` environment variable is set at the top of `agent.py` to redirect the Ollama client from `localhost` to `host.docker.internal:11434`, which is the address Docker uses to reach the host machine from inside a container.

### 4.3 Tool Registry and Tool Class

All tools are defined using a `Tool` dataclass with four fields: `name`, `description`, `parameters` (a JSON schema dict), and `function` (the Python callable). The `to_ollama_schema()` method converts a `Tool` into the format Ollama expects for its `tools` parameter:

```python
{
    "type": "function",
    "function": {
        "name": ...,
        "description": ...,
        "parameters": {"type": "object", "required": [...], "properties": {...}}
    }
}
```

The `ToolRegistry` class stores all registered tools and provides `to_ollama_tools()` which returns the full list of schemas. This design keeps tool definitions makes it easy to add or remove.

### 4.4 Tools Implemented

**Calculator**  Uses Python's `ast` module to parse a mathematical expression and evaluate it using only a whitelist of safe operations (`+`, `-`, `*`, `/`, `**`, `%`, `//`). This avoids the security risk of using `eval()` directly on user input.

**Web Search**  Uses the DuckDuckGo Search API (`ddgs` library) to perform a text search and return the top 5 results with title, snippet, and URL. DuckDuckGo was chosen because it requires no API key.

**Wikipedia**  Uses the `wikipedia-api` library to fetch the summary of a named article.

**Python Executor**  Writes the provided code to a temporary file and executes it as a subprocess with a 10-second timeout. Output is captured from `stdout`; errors from `stderr` are also returned so the agent can diagnose failures. The `tempfile.NamedTemporaryFile` approach ensures no code files are left on disk after execution.

**PDF Reader**  Uses `PyPDF2.PdfReader` to iterate over all pages of a PDF and extract their text, joining them into a single string. The agent can call this tool with a file path, or the Flask app can call it directly before passing text to the agent.

**Image Input**  The architecture supports image uploads. When an image is uploaded, the Flask app base64-encodes it and embeds it in the message using a `[IMAGE_DATA:...]` tag. The agent extracts this via `re.search` and constructs a multimodal Ollama message with the image attached. However, image processing was not fully tested in this submission as it requires a vision capable model (such as `llava` or `qwen2-vl`). The `qwen3:8b` model used here is text only. The implementation is in place and should work with a compatible model.

### 4.5 Agent Loop

The `run()` method implements the tool calling loop:

1. Check context length  if there are more than 20 messages, ask the model to summarise the conversation and replace the history with a single summary message. This prevents the context window from growing indefinitely.
2. Append the user message to `self.messages` (handling the image case separately)
3. Call `ollama.chat()` with the full message history and the tool schema list
4. If the response contains no tool calls, the model has produced a final answer  return it
5. If the response contains tool calls, execute each one, append the tool result to the message history with `role: "tool"`, and loop again
6. If the loop reaches `max_iterations` (default 8) without a final answer, return a fallback message

The key difference from a naive implementation is that `self.messages` is an instance variable that persists across calls, giving the agent a conversation memory within a session.

### 4.6 User Memory System

When a user sends a message starting with `"remember "`, the text following that keyword is extracted (using `message[9:]`) and written to the user's `user_config/25105693.json` file under the `"memories"` key. This file is read at startup and the memories are injected into the agent's system prompt:

```
Things you know about the user:
- I work at ....
- My favourite language is .....
```

This gives the agent persistent context that survives container restarts.


## 5. Docker Containerisation

### 5.1 Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "180", "app:app"]
```

Several deliberate choices were made here:

- **`python:3.13-slim`**  the `-slim` variant omits build tools and documentation, significantly reducing image size compared to the full image
- **Copy `requirements.txt` before `COPY . .`**  this leverages Docker's layer cache. As long as `requirements.txt` doesn't change, the `pip install` layer is reused on rebuilds, which makes subsequent builds much faster
- **Gunicorn instead of `app.run()`**  as covered in the lectures, `app.run()` uses Flask's development server which is single-threaded and not suitable for production. Gunicorn is a proper WSGI server. Two workers are configured with a 180 second timeout the long timeout is necessary because LLM inference can take tens of seconds, and the default 30 second Gunicorn timeout threw errors in testing
- **`EXPOSE 5000`**  documents that the container listens on port 5000, which is then mapped to the host with `-p 5000:5000` at runtime

### 5.2 Running the Container

```bash
docker run -p 5000:5000 -v $(pwd):/app ai-chat-app`
```

The `-v $(pwd):/app` volume mount means the user config and history JSON files are written to the project directory on the host machine, not inside the temporary container filesystem. This ensures conversation history and memories persist across container restarts.


## 6. Key Design Decisions

### 6.1 Keeping the LLM on the Host

One significant architectural decision was to run the LLM on the host machine and have the container connect to it over the network, rather than running Ollama inside the container. Running the model inside the container would require either passing through GPU devices (complicated) or running entirely on CPU (very slow). By keeping Ollama on the host, the container remains lightweight and portable while still benefiting from whatever hardware the host provides.

### 6.2 Single Agent Instance at Startup

The agent is created once when Flask starts, rather than creating a new agent per request. This is the correct approach for maintaining conversation state each request appends to the same `self.messages` list. A new instance per request would lose all conversation history between turns.

The trade off with this approach is that two simultaneous users would corrupt the message history. For a production deployment serving many users, each session would need its own agent instance.

### 6.3 File Upload Handling with tempfile

Uploaded files are saved to `tempfile.NamedTemporaryFile` paths rather than a permanent uploads directory. This avoids accumulating files on disk and removes the need to manage cleanup. The PDF reader reads from the temp path and the file is deleted immediately after. For images, the file is read, base64-encoded into a string, and the temp file deleted  the encoded data travels through the message pipeline as text.

### 6.4 Tool Result Truncation

Tool results are truncated at 2,000 characters before being appended to the message history. Without this, a large Wikipedia article or a long web search result could overflow the model's context window on the next iteration, causing inference to fail


## 7. Challenges and Solutions

### 7.1 Docker Cannot Connect to Ollama

**Problem:** When the container started, agent calls failed immediately because the Ollama client tried to connect to `localhost:11434`, which inside the container is the container itself  not the host machine.

**Solution:** Setting `os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"` at the top of `agent.py` redirects all Ollama client calls to the host machine's port 11434. The `--add-host=host.docker.internal:host-gateway` flag in the `docker run` command ensures this hostname resolves correctly on Linux.

### 7.2 Agent Not Using Saved Memories

**Problem:** The user could save memories (e.g., "remember I work at ....") and they would persist to JSON correctly, but asking "where do I work?" would produce a generic response.

**Root cause:** The agent was created at startup with an empty system prompt. Memories saved during that session were written to the JSON file but the already running agent had no way of knowing about them.

**Solution:** Added a `memories` parameter to `NativeToolAgent.__init__()` and `create_agent()`. The `load_memories()` function reads the JSON file at startup and passes the list to `create_agent()`, which injects them into the system prompt as a bulleted list under "Things you know about the user".

### 7.3 Variable Scope: `messages` vs `self.messages`

**Problem:** During conversion from a Jupyter notebook to a Python module, a local variable `messages` shadowed `self.messages` inside the agent, causing conversation history to reset on every call.

**Solution:** Carefully audited all references to ensure the instance variable `self.messages` is used consistently throughout the `run()` method. This is a common notebook to module issue because notebooks treat all variables as global.

### 7.4 Gunicorn Timeout Killing Requests

**Problem:** The first deployment with default Gunicorn settings killed LLM requests after 30 seconds with a `[CRITICAL] WORKER TIMEOUT` error.

**Solution:** Added `--timeout 180` to the Gunicorn command in the Dockerfile `CMD` instruction, giving each request up to 3 minutes to complete. This is appropriate for a single user local deployment.


## 8. Deployment Considerations

This application was built and tested as a local Docker deployment. The module covered several paths to take an application like this into production:

### 8.1 Why Not Cloud PaaS for This Application

Cloud PaaS options like **AWS Elastic Beanstalk**  are well suited to stateless Flask APIs. Both auto manage the WSGI server (Gunicorn), load balancing, and scaling. However, this application has a hard dependency on a locally running Ollama process with a downloaded model. Deploying to EB or Azure would require either:

- Hosting the model on a cloud GPU instance and pointing the app at it over the network, or
- Replacing Ollama with a cloud inference API (e.g., OpenAI, Anthropic)

This is a meaningful architectural trade off: cloud hosting adds cost (GPU instances are expensive) but removes the requirement for the end user to have Ollama installed locally.

### 8.2 VPS with GPU

For a production version of this exact architecture, the most suitable option would be a **GPU-equipped VPS**, such as a DigitalOcean GPU Droplet. The deployment pattern would be:

1. Provision a VPS with a suitable GPU
2. Install Ollama and pull the model on the VPS
3. Run the Docker container on the same VPS 
4. Use Nginx as a reverse proxy to terminate HTTP at port 80/443 and forward to Gunicorn on port 5000
5. Configure a systemd service to keep the container running

This would give a publicly accessible application with the model running entirely on the server.

### 8.3 Scaling Limitations

The current single agent instance design means the app supports only one concurrent user correctly. For a multi user production system, each user session would need its own agent instance. This could be implemented by storing agent state in a server side session store (e.g., Redis), session ID acting as the key


## 9. Conclusion

This project successfully delivers a functioning AI chat assistant that demonstrates the core deployment concepts from the module: Flask routing and request handling, Docker containerisation with layer caching and Gunicorn, and the practical challenges of connecting containerised applications to external services. The agent design extends the Week 10 lab with five tools, persistent conversation history, context summarisation, and a user memory system backed by JSON file storage.

The main limitations are the single user concurrency model and the dependency on a host side Ollama installation. Both could be resolved for production use, the former by introducing session scoped agent instances, the latter by deploying to a GPU VPS with Ollama running on the same machine. The application runs correctly end to end as submitted, fulfilling the assignment requirements.
