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
        # First, try to get the default branch if base_branch is not specified
        if base_branch == "main":
            base_branch = repo.default_branch

        # Get the latest commit on the base branch
        base_commit = repo.get_branch(base_branch).commit
        
        # Create a new branch name
        new_branch_name = f"{new_branch_prefix}{int(time.time())}"
        
        # Create the new branch
        repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_commit.sha)
        
        print(f"Created new branch: {new_branch_name}")
        return new_branch_name
    except GithubException as e:
        print(f"Failed to create branch. Status: {e.status}, Data: {e.data}")
        if e.status == 404:
            print(f"The base branch '{base_branch}' was not found. Please check if it exists in the repository.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while creating the branch: {str(e)}")
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
        # Check if there are any differences between the branches
        comparison = repo.compare(base_branch, head_branch)
        if not comparison.files:
            print(f"No differences found between {base_branch} and {head_branch}. Skipping pull request creation.")
            return None

        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        print(f"Created pull request: {pr.html_url}")
        return pr
    except GithubException as e:
        print(f"Failed to create pull request: {e.status} - {e.data.get('message', '')}")
        if e.status == 422 and "Validation Failed" in e.data.get('message', ''):
            print("This might be due to no changes between branches or an invalid base branch.")
        return None

def setup_and_update_branch(repo, modified_files, base_branch="main", issue_number=None):
    """Set up a new branch, update files, and create a pull request."""
    try:
        # Ensure we're using the correct base branch
        base_branch = repo.default_branch if base_branch == "main" else base_branch
        print(f"Using base branch: {base_branch}")

        new_branch = create_branch(repo, base_branch)
        if not new_branch:
            return False, "Failed to create new branch. Please check the repository permissions and branch names.", None

        files_updated = False
        for file_path, content in modified_files.items():
            try:
                update_file(repo, file_path, content, new_branch, f"Update {file_path}")
                files_updated = True
            except Exception as e:
                print(f"Failed to update file {file_path}: {str(e)}")

        if not files_updated:
            print("No files were updated. Skipping pull request creation.")
            return False, "No files were updated. Changes might already exist in the repository.", None

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
