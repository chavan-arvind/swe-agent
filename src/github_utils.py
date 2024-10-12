from github import Github, Auth, GithubException
from github.GithubException import UnknownObjectException
import os
import sys
import re

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

# Add other GitHub-related functions here
