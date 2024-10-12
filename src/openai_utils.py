from openai import OpenAI
from dotenv import load_dotenv
import os
import sys
import json
from openai.types.chat import ChatCompletion
from .file_utils import truncate_file_contents  # Add this import

def setup_openai_client():
    """Set up and return an OpenAI client instance."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key not found. Please check your .env file.")
        sys.exit(1)
    return OpenAI(api_key=api_key)

def plan_issue_resolution(client, issue_title: str, issue_body: str, file_contents: dict) -> tuple[str, dict]:
    """
    Create a plan for resolving the given GitHub issue, considering relevant file contents.
    """
    truncated_contents = truncate_file_contents(file_contents)
    prompt = f"""Plan to resolve the following issue:

Title: {issue_title}

Description: {issue_body}

Relevant files and their contents (truncated):
{json.dumps(truncated_contents, indent=2)}

Analyze the issue and the relevant file contents. Then provide your response as a structured JSON-like string with the following keys:
issue_analysis (a string summarizing the issue),
subtasks (a list of objects with description and estimated_time),
dependencies (a list of strings),
potential_challenges (a list of strings),
testing_strategy (a string),
and documentation_updates (a list of strings).
Ensure that all fields are present and in the correct format.
"""
    messages = [
        {"role": "system", "content": "You are a helpful and experienced software development planning agent."},
        {"role": "user", "content": prompt}
    ]
    response: ChatCompletion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    content = response.choices[0].message.content
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    return content, usage

# Add other OpenAI-related functions here
