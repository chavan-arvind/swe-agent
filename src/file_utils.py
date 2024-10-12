import json
import os
import base64
from github import GithubException

def truncate_file_contents(file_contents, max_chars_per_file=1000, max_total_chars=10000):
    truncated_contents = {}
    total_chars = 0
    for file_path, content in file_contents.items():
        if total_chars >= max_total_chars:
            break
        truncated_content = content[:max_chars_per_file]
        truncated_contents[file_path] = truncated_content
        total_chars += len(truncated_content)
    return truncated_contents

def get_local_repo_structure(repo_name):
    """Check if a local repository structure file exists and return its contents."""
    filename = f"{repo_name.replace('/', '_')}_structure.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return None

def save_repo_structure(structure, repo_name):
    """Save the repository structure as a JSON file."""
    if structure:
        filename = f"{repo_name.replace('/', '_')}_structure.json"
        with open(filename, 'w') as f:
            json.dump(structure, f, indent=2)
        print(f"Repository structure saved to {filename}")
    else:
        print("No structure to save.")

def get_file_content(repo, file_path):
    """Fetch the content of a file from the repository."""
    try:
        file_content = repo.get_contents(file_path)
        raw_content = base64.b64decode(file_content.content)
        
        # Try UTF-8 decoding first
        try:
            return raw_content.decode('utf-8')
        except UnicodeDecodeError:
            # If UTF-8 fails, try other common encodings
            for encoding in ['latin-1', 'ascii', 'iso-8859-1']:
                try:
                    return raw_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # If all decodings fail, return a placeholder for binary content
            return f"[Binary content, size: {len(raw_content)} bytes]"
    except GithubException as e:
        print(f"Error fetching file {file_path}: {e}")
        return None

# Add other file-related functions here
