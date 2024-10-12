import json
import re
import time
import difflib
import astroid
from github import GithubException
from .models import ResolutionPlan

def parse_ai_response(response: str) -> dict:
    """Parse and clean up the AI's response."""
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract content between triple backticks
        content = re.search(r'```json\n(.*?)```', response, re.DOTALL)
        if content:
            try:
                data = json.loads(content.group(1))
            except json.JSONDecodeError:
                raise ValueError("Unable to parse AI response as JSON")
        else:
            raise ValueError("Unable to parse AI response as JSON")
    
    # Handle nested issue_analysis
    if isinstance(data.get('issue_analysis'), dict):
        data['issue_analysis'] = data['issue_analysis'].get('description', str(data['issue_analysis']))
    
    # Ensure certain fields are lists
    for field in ['dependencies', 'potential_challenges', 'documentation_updates']:
        if field in data and not isinstance(data[field], list):
            data[field] = [data[field]]
    
    # Ensure subtasks is a list of dicts
    if 'subtasks' in data and not isinstance(data['subtasks'], list):
        data['subtasks'] = [data['subtasks']]
    
    return data

def remove_unused_imports(content):
    tree = astroid.parse(content)
    used_names = set()
    for node in tree.body:
        if isinstance(node, astroid.Import) or isinstance(node, astroid.ImportFrom):
            continue
        for name in node.nodes_of_class(astroid.Name):
            used_names.add(name.name)
    
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            module = line.split()[1]
            if module in used_names:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    return '\n'.join(new_lines)

def modify_files(repo, file_contents, plan):
    """Modify the files based on the resolution plan."""
    modified_files = {}
    for file_path, content in file_contents.items():
        if file_path.endswith('.py'):
            modified_content = remove_unused_imports(content)
            if modified_content != content:
                modified_files[file_path] = modified_content
                print(f"Modified file: {file_path}")
                print("Changes made:")
                print("\n".join(difflib.unified_diff(content.splitlines(), modified_content.splitlines(), lineterm='')))
    return modified_files

def create_pull_request(repo, issue, modified_files):
    """Create a new branch and pull request with the modified files."""
    try:
        # Create a new branch
        base_branch = repo.default_branch
        timestamp = int(time.time())
        new_branch_name = f"fix-issue-{issue.number}-{timestamp}"
        
        # Get the latest commit on the base branch
        base_sha = repo.get_branch(base_branch).commit.sha
        
        # Create the new branch
        repo.create_git_ref(f"refs/heads/{new_branch_name}", base_sha)
        
        # Update files in the new branch
        for file_path, new_content in modified_files.items():
            try:
                contents = repo.get_contents(file_path, ref=new_branch_name)
                repo.update_file(
                    path=file_path,
                    message=f"Update {file_path}",
                    content=new_content,
                    sha=contents.sha,
                    branch=new_branch_name
                )
            except GithubException as e:
                if e.status == 404:  # File doesn't exist, so create it
                    repo.create_file(
                        path=file_path,
                        message=f"Create {file_path}",
                        content=new_content,
                        branch=new_branch_name
                    )
                else:
                    raise
        
        # Create a pull request
        pr = repo.create_pull(
            title=f"Fix for issue #{issue.number}: {issue.title}",
            body=f"This pull request addresses issue #{issue.number}. Please review and merge if appropriate.",
            head=new_branch_name,
            base=base_branch
        )
        print(f"Pull request created: {pr.html_url}")
        return pr
    except GithubException as e:
        print(f"Error creating pull request: {e.status} - {e.data.get('message', 'Unknown error')}")
        return None
    except Exception as e:
        print(f"Unexpected error in create_pull_request: {str(e)}")
        return None

# Add other issue resolution related functions here
