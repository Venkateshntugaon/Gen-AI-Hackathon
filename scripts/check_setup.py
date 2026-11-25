"""Checks that the project is set up correctly before you run the app.

It loads .env, sends one tiny prompt to Gemini and prints "Gemini OK: <model>".
If the model name in .env is wrong, it lists the model names your key can use,
so you can fix GEMINI_MODEL. The API key itself is never printed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google import genai

from src.reviewer import config


def list_model_names(client: genai.Client) -> list[str]:
    """Return the names of models that can generate text with this key."""
    names = []
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(model.name.removeprefix("models/"))
    return names


def main() -> None:
    try:
        api_key = config.get_api_key()
    except RuntimeError as error:
        print(error)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    try:
        client.models.generate_content(model=config.GEMINI_MODEL, contents="Reply with the word OK.")
    except Exception as error:
        print(f"Gemini call failed for model '{config.GEMINI_MODEL}': {type(error).__name__}")
        if "not found" in str(error).lower() or "404" in str(error):
            print("Available model names (put one in GEMINI_MODEL in .env):")
            for name in list_model_names(client):
                print(f"  - {name}")
        sys.exit(1)

    print(f"Gemini OK: {config.GEMINI_MODEL}")


if __name__ == "__main__":
    main()
