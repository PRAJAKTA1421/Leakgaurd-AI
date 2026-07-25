# Leakgaurd-AI

## Mistral chatbot setup

The floating robot chatbot calls Mistral from the Flask server, so your API key stays private. Create a private file named `.env` beside `app.py` (not `.env.example`) and add your key there:

```text
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_MODEL=mistral-small-latest
```

Restart `python app.py` after saving `.env`. The app automatically loads this private file, which is excluded from Git. Never put a real API key in `.env.example` or commit it.
