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
    truncated_contents = truncate_file_contents(file_contents)
    project_type = determine_project_type(file_contents.keys())
    
    api_files = [file for file in file_contents.keys() if any(keyword in file.lower() for keyword in ['api', 'route', 'endpoint', 'controller'])]
    test_files = [file for file in file_contents.keys() if 'test' in file.lower() or 'spec' in file.lower()]
    
    prompt = f"""Plan to resolve the following issue for a {project_type} project:

Title: {issue_title}

Description: {issue_body}

API-related files:
{json.dumps(api_files, indent=2)}

Existing test files:
{json.dumps(test_files, indent=2)}

Relevant file contents (truncated):
{json.dumps(truncated_contents, indent=2)}

Analyze the issue, focusing on adding tests for API endpoints if required. Then provide your response as a structured JSON-like string with the following keys:
issue_analysis (a string summarizing the issue),
subtasks (a list of objects with description and estimated_time),
dependencies (a list of strings),
potential_challenges (a list of strings),
testing_strategy (a string),
and documentation_updates (a list of strings).

For each subtask, provide specific details on how to implement the changes or tests, including:
1. Which API endpoint to test or modify
2. What test cases to create (e.g., successful requests, error handling, edge cases)
3. Any new test files that need to be created
4. Any modifications required to existing files

Ensure that all fields are present and in the correct format.
"""
    messages = [
        {"role": "system", "content": f"You are a helpful and experienced software development planning agent, specialized in {project_type} projects."},
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

def determine_project_type(file_paths):
    js_count = sum(1 for path in file_paths if path.endswith(('.js', '.ts')))
    cs_count = sum(1 for path in file_paths if path.endswith('.cs'))
    py_count = sum(1 for path in file_paths if path.endswith('.py'))
    
    if js_count > cs_count and js_count > py_count:
        return "Node.js"
    elif cs_count > js_count and cs_count > py_count:
        return ".NET"
    else:
        return "Python"

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    return OpenAI(api_key=api_key)

# Add other OpenAI-related functions here
