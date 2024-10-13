from github import Github, Auth, GithubException
from github.GithubException import UnknownObjectException
import os
import sys
import re
import requests

def setup_github_client():
    """Set up and return a GitHub client instance."""
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GitHub token not found. Please check your .env file.")
        sys.exit(1)
    auth = Auth.Token(github_token)
    client = Github(auth=auth)
    try:
        # Verify the token by attempting to fetch the authenticated user
        user = client.get_user().login
        print(f"Authenticated as GitHub user: {user}")
    except GithubException as e:
        print(f"Error authenticating with GitHub: {e.status} - {e.data.get('message', 'Unknown error')}")
        print("Please check your GitHub token and ensure it has the necessary permissions.")
        sys.exit(1)
    return client

def parse_repo_url(url):
    """Parse the repository owner and name from a GitHub URL."""
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, url)
    if match:
        return f"{match.group(1)}/{match.group(2).rstrip('.git')}"
    return None

def get_repo_issues(github_client, repo_name):
    """Fetch open issues from the specified GitHub repository."""
    try:
        repo = github_client.get_repo(repo_name)
        issues = list(repo.get_issues(state='open'))
        if not issues:
            print(f"The repository '{repo_name}' doesn't have any open issues.")
        return issues
    except UnknownObjectException:
        print(f"Error: The repository '{repo_name}' was not found. It might be private or doesn't exist.")
    except GithubException as e:
        print(f"GitHub API error: {e.status} - {e.data.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    return []

def setup_codespace_for_testing(repo, branch="main"):
    """Set up a Codespace for testing, run tests, and clean up."""
    print(f"Setting up Codespace for testing branch: {branch}")
    return setup_and_test_codespace(repo, branch)

def get_repo_structure(github_client, repo_name):
    """Fetch the repository structure from GitHub."""
    try:
        repo = github_client.get_repo(repo_name)
        contents = repo.get_contents("")
        structure = {"name": repo.name, "type": "directory", "children": []}
        
        def traverse_contents(contents, current_dir):
            for content in contents:
                if content.type == "dir":
                    new_dir = {"name": content.name, "type": "directory", "children": []}
                    current_dir["children"].append(new_dir)
                    traverse_contents(repo.get_contents(content.path), new_dir)
                else:
                    current_dir["children"].append({"name": content.name, "type": "file"})
        
        traverse_contents(contents, structure)
        return structure
    except Exception as e:
        print(f"An error occurred while fetching repository structure: {str(e)}")
        return None

# Add other GitHub-related functions here
