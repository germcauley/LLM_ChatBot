from flask import Flask, request, render_template,jsonify # This imports Flask for creating the web application, request for reading incoming HTTP data, and render_template for rendering an HTML template with variables.
import json,os,datetime,tempfile
from agent import create_agent, read_pdf

# constants to help with memory and user identity
USER_ID = "25105693"
USER_NAME = "Gerald McAuley"
USER_CONFIG_PATH = f"user_config/{USER_ID}.json"
HISTORY_PATH = f"{USER_ID}_history.json"




app = Flask(__name__)


def load_or_create_files():
        # check if the user files we need exist
    if not os.path.exists(USER_CONFIG_PATH):
        # create the user config files
        with open(USER_CONFIG_PATH, "w") as f:
            default_content = {
            "user_id": "25105693",
            "user_name": "Gerald McAuley",
            "memories": [],
            "conversation_summary": ""
            }
            json.dump(default_content, f,indent=2)
    if not os.path.exists(HISTORY_PATH):
        # create the history file as an empty list
        with open(HISTORY_PATH, "w") as f:
            json.dump([], f,indent=2) 
        
load_or_create_files()
agent = create_agent()

# setup first route
@app.route("/", methods=["GET"])
def home():
        return render_template("index.html",)
 
@app.route("/chat", methods=["POST"])
def chat():
    # get the message from the form frontend
    message = request.form.get("message", "")
    # error handling for empty message
    if not message.strip():
        return jsonify({"error": "Empty message"}), 400
    # check if its a memory command
    if message.lower().startswith("remember "):
        memory = message[9:] # read everything after remember into memory
        # read the memory from our user config
        with open(USER_CONFIG_PATH, "r") as f:
            config = json.load(f)
            # append the memory to f
        config["memories"].append(memory)
        # update the config memory
        with open(USER_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return jsonify({"reply": f"Ok, I'll remember: {memory}"})
    else:
        # the file we upload, returns none if no file
        file = request.files.get("file")
        
        # check filetype
        if file:
            filename = file.filename.lower()
            if filename.endswith(".pdf"):
                # handle PDF use the pdf tool, read using tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    file.save(tmp.name)
                    # use our pdf tool from our agent
                    pdf_text = read_pdf(tmp.name)
                    os.unlink(tmp.name)  # delete temp file after reading
                    message = message + f"\n\nPDF Content:\n{pdf_text}"
            elif filename.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        # handle image files
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    file.save(tmp.name)
                with open(tmp.name, "rb") as img_file:
                    image_data = base64.b64encode(img_file.read()).decode("utf-8")
                os.unlink(tmp.name)
                message = message + f"\n\n[IMAGE_DATA:{image_data}]"

        answer, trace = agent.run(message)
        
        
        # save to history
        with open(HISTORY_PATH, "r") as f:
            history = json.load(f)

        history.append({
            "datetime": datetime.datetime.now().isoformat(),
            "user_id": USER_ID,
            "prompt": message,
            "agent": "NativeToolAgent",
            "reply": answer,
            "trace":trace
            })

        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)
    # return the response
    return jsonify({"reply": answer})
         
@app.route("/reset", methods=["POST"])
def reset():
    agent.reset()
    return jsonify({"status": "conversation reset"})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
