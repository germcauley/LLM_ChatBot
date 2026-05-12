from flask import Flask, request, render_template # This imports Flask for creating the web application, request for reading incoming HTTP data, and render_template for rendering an HTML template with variables.
import json,os,datetime
from agent import create_agent
from PIL import Image # Pill is a common library for loading and manipulating images

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
            history_file = []
            json.dump(history_file, f,indent=2) 
        
load_or_create_files()
agent = create_agent()

# setup first route
@app.route("/", methods=["GET"])

def home():
    if request.method == "GET":
        return render_template("index.html",)
 
   