import requests
import time
import os
from urllib.parse import quote
from github import GithubException

GITHUB_API_BASE = "https://api.github.com"
MAX_RETRIES = 3
RETRY_DELAY = 5

def get_github_token():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise Exception("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
    return token

def create_branch(repo, base_branch="main", new_branch_prefix="fix-issue-"):
    """Create a new branch in the given repository."""
    try:
        base_ref = repo.get_git_ref(f"heads/{base_branch}")
        new_branch_name = f"{new_branch_prefix}{int(time.time())}"
        repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_ref.object.sha)
        print(f"Created new branch: {new_branch_name}")
        return new_branch_name
    except GithubException as e:
        print(f"Failed to create branch: {e}")
        return None

def update_file(repo, file_path, content, branch, commit_message):
    """Update a file in the repository on the specified branch."""
    try:
        contents = repo.get_contents(file_path, ref=branch)
        repo.update_file(contents.path, commit_message, content, contents.sha, branch=branch)
        print(f"Updated file: {file_path}")
    except GithubException as e:
        if e.status == 404:  # File doesn't exist, so create it
            repo.create_file(file_path, commit_message, content, branch=branch)
            print(f"Created new file: {file_path}")
        else:
            print(f"Failed to update file {file_path}: {e}")

def create_pull_request(repo, head_branch, base_branch="main", title="", body=""):
    """Create a pull request from the head branch to the base branch."""
    try:
        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        print(f"Created pull request: {pr.html_url}")
        return pr
    except GithubException as e:
        print(f"Failed to create pull request: {e}")
        return None

def setup_and_update_branch(repo, modified_files, base_branch="main", issue_number=None):
    """Set up a new branch, update files, and create a pull request."""
    try:
        new_branch = create_branch(repo, base_branch)
        if not new_branch:
            return False, "Failed to create new branch", None

        for file_path, content in modified_files.items():
            update_file(repo, file_path, content, new_branch, f"Update {file_path}")

        pr_title = f"Fix for issue #{issue_number}" if issue_number else "Update files"
        pr_body = f"This pull request addresses issue #{issue_number}." if issue_number else "This pull request updates files."
        pr = create_pull_request(repo, new_branch, base_branch, title=pr_title, body=pr_body)

        if pr:
            return True, f"Branch '{new_branch}' created, files updated, and pull request created", pr.html_url
        else:
            return False, f"Branch '{new_branch}' created and files updated, but failed to create pull request", None
    except Exception as e:
        return False, f"An error occurred: {str(e)}", None

# Add this line at the end of the file
__all__ = ['setup_and_update_branch', 'create_branch', 'update_file', 'create_pull_request']
