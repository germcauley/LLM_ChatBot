# Project Title
An AI chat assistant built using Flask running inside a Docker container. It uses a locally hosted LLM (qwen3:8b via Ollama) as its brain and exposes a browser based chat interface.

What it can do:

- Answer general questions using the LLM
- Search the web via DuckDuckGo
- Look up Wikipedia articles
- Perform calculations safely
- Write and execute Python code
- Read and summarise PDF files uploaded by the user
- Remember facts about the user across sessions eg ("remember I work at X)

## How it works:
The browser sends messages to a Flask backend via fetch(). Flask passes the message to a NativeToolAgent which uses Ollama's native function calling API to decide whether to answer directly or call one of the tools. The response is returned as JSON and rendered in the chat using marked.js for markdown support.

Persistence:

User memories stored in user_config/25105693.json
Full conversation history logged to 25105693_history.json
Conversation summarised automatically when it exceeds 20 messages
## Stack:

Python, Flask, Gunicorn
Ollama (qwen3:8b)
Docker
Vanilla HTML/CSS/JS with Press Start 2P font

## Requirements
- Docker installed and running
- Ollama installed and running on the host machine
- qwen3:8b model pulled via Ollama (ollama pull qwen3:8b)
- No other dependencies needed, everything else runs inside Docker

## Setup & Installation
- Clone the project
- Build the Docker image: `docker build -t ai-chat-app .`
- Run the container (run this command from inside the project folder):
`docker run -p 5000:5000 -v $(pwd):/app ai-chat-app`
- Linux users: add `--add-host=host.docker.internal:host-gateway` to the run command so the container can reach Ollama on the host machine
- Once the container is running, open your browser and go to: http://localhost:5000

## How to Use
- Type a message in the chat and press enter or click send
- It can search the web, perform calcuation, lookup wikipedia and wite and eecute python code
- You can type 'remember' before anything you submit and the chat will add it to memory and remember it later if you ask
- You can upload a pdf file using the Paperclip icon and ask the chat to do something with it, by default (blank message) it will analyse the file
- You can clear the chat history using the reset button

## Project Structure

```
Model_deployment_assignment3/
├── .gitignore
├── Dockerfile
├── README.md
├── agent.py
├── app.py
├── requirements.txt
├── technical_report.md
├── 25105693_history.json
├── static/
│   └── icons/
│       ├── clip.svg
│       └── computer.svg
├── templates/
│   └── index.html
└── user_config/
    └── 25105693.json
```

## References
- Week 8 Lab - Flask web application (used as reference for Flask route structure)
- Week 10 Lab - Building an AI Agent (foundation for the NativeToolAgent and tools)
- Flask Documentation - https://flask.palletsprojects.com/
- Ollama Documentation - https://ollama.com/
- PyPDF2 Documentation - https://pypdf2.readthedocs.io/
- DuckDuckGo Search API (ddgs) - https://github.com/deedy5/duckduckgo_search

## AI Usage Disclosure

I used Claude by Anthropic during this project in a similar way to how I would use Google search. I wrote all the code myself or copied from previous labs, which are documented in notes.md.

Specific examples of how I used it:

- Generated the project structure tree for the README
- Generated the architecture diagram for the technical report

When the agent wasn't using saved memories, I diagnosed the root cause myself. The agent is instantiated once at startup with create_agent(), so any memories saved during a session were being written to JSON correctly but weren't reflected in the already running agent's system prompt. I used Claude to talk through the fix to make sure I was adding the parameter correctly and passing it inte correct place: adding a memories parameter to NativeToolAgent.__init__(), passing it through create_agent(), writing a load_memories() function in app.py to read from JSON at startup, and rewording the system prompt injection so the model didn't give "I don't have personal data" responses.

For the HTML and CSS, I made my own design decisions. The final UI is a custom bare bones interface I built myself. I used Claude to understand specific CSS properties when I wasn't sure of the syntax eg formatting code output in a different colour to text output.

## What I did not use it for

I did not use Claude to generate the core architecture, the agent loop, the tool implementations, or the Flask routes. The NativeToolAgent class, ToolRegistry, Tool dataclass, and all five tools came directly from the lab work which I extended myself. The decision to use Ollama, to run the model on the host rather than inside the container, to use tempfile for file uploads, and to store history and memories as JSON files were all my own decisions.

I found Claude helpful for talking through bugs where I had already formed a theory and wanted to confirm it before making changes. It saved time but did not replace my own understanding of the code.

## Prompts used during Debugging & fixes

- Why can't my Docker container connect to Ollama?
- Why is the agent not using saved memories?
- Why is base64 not found?
- Gunicorn worker timeout killing requests, what does that mean?
- Agent introduces itself as the user instead of talking about the user, how to fix the system prompt?

## Understanding concepts

- What does global agent do?
- What are the pros and cons of running the model on the container or host?

## UI / HTML

- How do I render markdown in the chat response?
- How do I serve SVG icons from Flask?
- How do I apply this Google font?

## Documentation

- Generate a project structure tree for the README
- Generate a basic architecture diagram
- Check for spelling errors
