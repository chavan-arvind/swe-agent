import requests
import time
import os
from urllib.parse import quote

GITHUB_API_BASE = "https://api.github.com"
MAX_RETRIES = 3
RETRY_DELAY = 5

def get_github_token():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise Exception("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
    return token

def make_github_request(method, url, headers=None, json=None, max_retries=MAX_RETRIES):
    if headers is None:
        headers = {
            "Authorization": f"token {get_github_token()}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, headers=headers, json=json)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            print(f"Request failed: {e}. Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

def create_codespace(repo, branch="main"):
    """Create a new Codespace for the given repository and branch."""
    print("Creating Codespace... This may take a few minutes.")
    url = f"{GITHUB_API_BASE}/repos/{repo.full_name}/codespaces"
    data = {
        "ref": branch,
        "location": "WestUs2"  # You can change this to your preferred location
    }
    response = make_github_request("POST", url, json=data)
    codespace = response.json()
    print(f"Codespace created: {codespace['name']}")
    return codespace

def wait_for_codespace_ready(codespace):
    """Wait for the Codespace to be ready."""
    print("Waiting for Codespace to be ready...")
    start_time = time.time()
    url = f"{GITHUB_API_BASE}/user/codespaces/{codespace['name']}"
    while True:
        response = make_github_request("GET", url)
        state = response.json()['state']
        if state == 'ready':
            print(f"Codespace is ready! State: {state}")
            return True
        elif time.time() - start_time > 600:  # 10 minutes timeout
            print("Timeout waiting for Codespace to be ready.")
            return False
        print(f"Waiting for Codespace to be ready. Current state: {state}")
        time.sleep(15)

def run_command_in_codespace(codespace, command):
    """Run a command in the given Codespace and return results."""
    url = f"{GITHUB_API_BASE}/user/codespaces/{codespace['name']}/console-sessions"
    data = {
        "command": command,
        "workingDirectory": "/workspaces/repo"
    }
    response = make_github_request("POST", url, json=data)
    session = response.json()
    
    # Poll for command completion
    poll_url = f"{GITHUB_API_BASE}/user/codespaces/{codespace['name']}/console-sessions/{session['id']}"
    while True:
        response = make_github_request("GET", poll_url)
        if response.json()['status'] == 'completed':
            break
        time.sleep(2)
    
    # Get the output
    output_url = f"{GITHUB_API_BASE}/user/codespaces/{codespace['name']}/console-sessions/{session['id']}/output"
    response = make_github_request("GET", output_url)
    return True, response.text

def setup_and_test_codespace(repo, branch="main"):
    """Set up a Codespace, run tests, and clean up."""
    try:
        codespace = create_codespace(repo, branch)
        if not codespace:
            return False, "Failed to create Codespace"

        if not wait_for_codespace_ready(codespace):
            return False, "Codespace failed to become ready"

        print("Installing dependencies...")
        success, output = run_command_in_codespace(codespace, "pip install -r requirements.txt")
        if not success:
            return False, f"Failed to install dependencies: {output}"

        print("Running tests...")
        success, output = run_command_in_codespace(codespace, "pytest")
        
        return success, output
    except Exception as e:
        return False, f"An error occurred: {str(e)}"
    finally:
        if 'codespace' in locals():
            delete_codespace(codespace['name'])

def delete_codespace(codespace_name):
    """Delete the given Codespace."""
    print(f"Deleting Codespace {codespace_name}...")
    url = f"{GITHUB_API_BASE}/user/codespaces/{quote(codespace_name)}"
    try:
        make_github_request("DELETE", url)
        print(f"Codespace {codespace_name} deleted successfully")
        return True
    except Exception as e:
        print(f"Failed to delete Codespace: {str(e)}")
        return False

# Add this line at the end of the file
__all__ = ['setup_and_test_codespace', 'create_codespace', 'run_command_in_codespace', 'delete_codespace']
