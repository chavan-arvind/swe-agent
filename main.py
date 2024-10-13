import sys
from dotenv import load_dotenv
from github import GithubException
from src.github_utils import (
    setup_github_client,
    parse_repo_url,
    get_repo_issues,
    setup_codespace_for_testing,
    get_repo_structure
)
from src.openai_utils import setup_openai_client, plan_issue_resolution
from src.file_utils import get_local_repo_structure, save_repo_structure, get_file_content
from src.models import ResolutionPlan
from src.issue_resolution import parse_ai_response, modify_files, create_pull_request
from src.codespace_utils import setup_and_test_codespace
from src.branch_utils import setup_and_update_branch  # Update this import
import requests

def display_issues(issues):
    """Display a list of issues with numbers for selection."""
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue.title}")

def get_user_selection(max_value):
    """Get and validate user input for issue selection."""
    while True:
        try:
            selection = int(input(f"Enter the number of the issue (1-{max_value}) or 0 to quit: "))
            if 0 <= selection <= max_value:
                return selection
            print(f"Please enter a number between 0 and {max_value}.")
        except ValueError:
            print("Please enter a valid number.")

def display_resolution_plan(plan: ResolutionPlan):
    """Display the resolution plan in a formatted manner."""
    print("\nIssue Resolution Plan:")
    print(f"\nIssue Analysis:\n{plan.issue_analysis}")
    
    print("\nSubtasks:")
    for i, subtask in enumerate(plan.subtasks, 1):
        print(f"{i}. {subtask.description} (Estimated time: {subtask.estimated_time})")
    
    print("\nDependencies:")
    for dependency in plan.dependencies:
        print(f"- {dependency}")
    
    print("\nPotential Challenges:")
    for challenge in plan.potential_challenges:
        print(f"- {challenge}")
    
    print(f"\nTesting Strategy:\n{plan.testing_strategy}")
    
    print("\nRecommended Documentation Updates:")
    for update in plan.documentation_updates:
        print(f"- {update}")

def get_or_fetch_repo_structure(github_client, repo_name):
    """Get the repository structure from local file or fetch from GitHub if not available."""
    local_structure = get_local_repo_structure(repo_name)
    if local_structure:
        print(f"Using existing repository structure from {repo_name.replace('/', '_')}_structure.json")
        return local_structure
    
    print("Fetching repository structure from GitHub...")
    return get_repo_structure(github_client, repo_name)

def find_relevant_files(repo, issue_title, issue_body):
    """Find files that might be relevant to the issue based on keywords."""
    keywords = set(issue_title.lower().split())
    if issue_body:
        keywords.update(issue_body.lower().split())
    relevant_files = []
    contents = repo.get_contents("")
    
    print(f"Searching for files with keywords: {keywords}")
    
    def traverse_contents(contents):
        for content in contents:
            if content.type == "dir":
                traverse_contents(repo.get_contents(content.path))
            elif content.type == "file":
                file_name = content.name.lower()
                file_path = content.path.lower()
                if any(keyword in file_name or keyword in file_path for keyword in keywords):
                    relevant_files.append(content.path)
                    print(f"Found relevant file: {content.path}")
    
    traverse_contents(contents)
    
    if not relevant_files:
        print("No relevant files found. Including all Python files.")
        traverse_contents(repo.get_contents(""))
        relevant_files = [content.path for content in contents if content.name.endswith('.py')]
    
    return relevant_files

def analyze_relevant_files(repo, relevant_files, max_file_size=100000):  # 100 KB limit
    """Analyze the content of relevant files."""
    file_contents = {}
    for file_path in relevant_files:
        try:
            file_content = repo.get_contents(file_path)
            if file_content.size > max_file_size:
                file_contents[file_path] = f"[File too large to analyze, size: {file_content.size} bytes]"
            else:
                content = get_file_content(repo, file_path)
                if content:
                    file_contents[file_path] = content
        except GithubException as e:
            print(f"GitHub API error for file {file_path}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Network error for file {file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error for file {file_path}: {e}")
    return file_contents

def main():
    load_dotenv()
    print("Welcome to the GitHub Issue Resolution Planner!")
    print("This tool will help you create plans for resolving GitHub issues and analyze repository structure.")
    print("You can enter '0' at any time to exit the program.\n")

    github_client = setup_github_client()
    openai_client = setup_openai_client()

    while True:
        repo_url = input("Enter the GitHub repository URL: ").strip()
        if repo_url.lower() == '0':
            print("Exiting the program. Goodbye!")
            sys.exit(0)

        repo_name = parse_repo_url(repo_url)
        if not repo_name:
            print("Invalid GitHub URL. Please try again.")
            continue

        # Get or fetch and save repository structure
        repo_structure = get_or_fetch_repo_structure(github_client, repo_name)
        if repo_structure:
            save_repo_structure(repo_structure, repo_name)
        else:
            print("Unable to fetch repository structure. Continuing without it.")

        issues = get_repo_issues(github_client, repo_name)
        if not issues:
            continue

        print("\nOpen Issues:")
        display_issues(issues)

        selection = get_user_selection(len(issues))
        if selection == 0:
            print("Exiting the program. Goodbye!")
            sys.exit(0)

        selected_issue = issues[selection - 1]
        print(f"\nAnalyzing relevant files for: {selected_issue.title}")
        print(f"Issue body: {selected_issue.body}")
        print("Please wait...\n")

        repo = github_client.get_repo(repo_name)
        relevant_files = find_relevant_files(repo, selected_issue.title, selected_issue.body)
        
        print(f"\nFound {len(relevant_files)} relevant files:")
        for file_path in relevant_files:
            print(f"- {file_path}")
        
        file_contents = analyze_relevant_files(repo, relevant_files)

        print(f"\nAnalyzed {len(file_contents)} files:")
        for file_path in file_contents.keys():
            print(f"- {file_path}")

        print(f"\nGenerating resolution plan for: {selected_issue.title}")
        print("Please wait...\n")

        try:
            plan_json, token_usage = plan_issue_resolution(openai_client, selected_issue.title, selected_issue.body, file_contents)
            plan_dict = parse_ai_response(plan_json)
            plan = ResolutionPlan(**plan_dict)
            display_resolution_plan(plan)

            # Ask user if they want to proceed with creating a new branch and pull request
            create_pr = input("Do you want to create a new branch and pull request with the proposed changes? (y/n): ").lower().strip()
            if create_pr == 'y':
                modified_files = modify_files(repo, file_contents, plan)
                success, message, pr_url = setup_and_update_branch(repo, modified_files, issue_number=selected_issue.number)
                if success:
                    print(message)
                    if pr_url:
                        print(f"Pull request created: {pr_url}")
                    else:
                        print("Pull request creation failed, but branch was created with changes.")
                else:
                    print(f"Failed to create branch and update files: {message}")
            else:
                print("Branch and pull request creation skipped.")

            print("\nToken Usage:")
            print(f"Prompt tokens: {token_usage['prompt_tokens']}")
            print(f"Completion tokens: {token_usage['completion_tokens']}")
            print(f"Total tokens: {token_usage['total_tokens']}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            import traceback
            print("Traceback:")
            print(traceback.format_exc())
        print("\n---\n")

if __name__ == "__main__":
    main()
