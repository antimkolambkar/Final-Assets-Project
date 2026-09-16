import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    print("Starting Enterprise IT Asset Management & Helpdesk System on http://127.0.0.1:5000 ...")

    # Check whether OpenAI API key is available
    if os.getenv("OPENAI_API_KEY"):
        print("OpenAI AI service: CONFIGURED")
    else:
        print("OpenAI AI service: NOT CONFIGURED")

    app.run(host='0.0.0.0', port=5000, debug=True)
