import json
import re
import time
import difflib
import astroid
import os
from github import GithubException
from .models import ResolutionPlan
from .openai_utils import get_openai_client

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

def remove_unused_imports(content, file_extension):
    if file_extension == '.py':
        return remove_unused_imports_python(content)
    elif file_extension == '.js' or file_extension == '.ts':
        return remove_unused_imports_js(content)
    elif file_extension == '.cs':
        return remove_unused_imports_csharp(content)
    else:
        return content

def remove_unused_imports_python(content):
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

def remove_unused_imports_js(content):
    # This is a simplified version and may need improvement
    lines = content.split('\n')
    used_imports = set()
    import_lines = []
    other_lines = []

    for line in lines:
        if line.strip().startswith('import ') or line.strip().startswith('const ') or line.strip().startswith('let '):
            import_lines.append(line)
            imported_name = line.split(' ')[1]
            if '{' in imported_name:
                imported_name = imported_name.split('{')[1].split('}')[0].strip()
            used_imports.add(imported_name)
        else:
            other_lines.append(line)
            for import_name in used_imports:
                if import_name in line:
                    used_imports.add(import_name)

    cleaned_imports = [line for line in import_lines if any(name in line for name in used_imports)]
    return '\n'.join(cleaned_imports + other_lines)

def remove_unused_imports_csharp(content):
    # This is a simplified version and may need improvement
    lines = content.split('\n')
    used_namespaces = set()
    import_lines = []
    other_lines = []

    for line in lines:
        if line.strip().startswith('using '):
            import_lines.append(line)
            namespace = line.split(' ')[1].rstrip(';')
            used_namespaces.add(namespace)
        else:
            other_lines.append(line)
            for namespace in used_namespaces:
                if namespace in line:
                    used_namespaces.add(namespace)

    cleaned_imports = [line for line in import_lines if any(namespace in line for namespace in used_namespaces)]
    return '\n'.join(cleaned_imports + other_lines)

def modify_files(repo, file_contents, plan):
    modified_files = {}
    openai_client = get_openai_client()

    print("Starting file modifications based on the resolution plan...")
    for subtask in plan.subtasks:
        print(f"Processing subtask: {subtask.description}")
        description = subtask.description.lower()
        if "create test file" in description:
            new_test_file = create_test_file(subtask.description, file_contents)
            if new_test_file:
                file_path, content = new_test_file
                modified_files[file_path] = content
                print(f"Created new test file: {file_path}")
        elif "update readme" in description or "update readme.md" in description:
            readme_path = "README.md"
            if readme_path in file_contents:
                updated_content = update_readme(file_contents[readme_path], subtask.description)
                if updated_content != file_contents[readme_path]:
                    modified_files[readme_path] = updated_content
                    print(f"Updated README file: {readme_path}")
            else:
                print("README.md not found in the repository. Creating a new one.")
                modified_files[readme_path] = create_readme(subtask.description)
                print(f"Created new README file: {readme_path}")
        else:
            for file_path, content in file_contents.items():
                if file_path.lower() in description.lower():
                    print(f"Modifying file: {file_path}")
                    modified_content = implement_changes_with_openai(openai_client, content, subtask.description, os.path.splitext(file_path)[1])
                    if modified_content != content:
                        modified_files[file_path] = modified_content
                        print(f"Modified file: {file_path}")
                    else:
                        print(f"No changes made to file: {file_path}")
    
    if not modified_files:
        print("No files were modified based on the resolution plan.")
        print("Subtasks:")
        for subtask in plan.subtasks:
            print(f"- {subtask.description}")
        print("Available files:")
        for file_path in file_contents.keys():
            print(f"- {file_path}")
    else:
        print("Files modified:")
        for file_path, content in modified_files.items():
            print(f"Changes in {file_path}:")
            print("\n".join(difflib.unified_diff(file_contents.get(file_path, '').splitlines(), content.splitlines(), lineterm='')))
    
    return modified_files

def implement_changes_with_openai(client, content, description, file_extension):
    prompt = f"""
    Given the following file content and change description, please modify the content according to the description.
    Only output the modified content, not any explanations.

    File content:
    ```{file_extension}
    {content}
    ```

    Change description: {description}

    Modified content:
    ```{file_extension}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that modifies code based on descriptions."},
            {"role": "user", "content": prompt}
        ]
    )

    modified_content = response.choices[0].message.content.strip()
    # Remove the opening and closing backticks and language identifier
    modified_content = re.sub(r'^```[\w-]*\n|```$', '', modified_content, flags=re.MULTILINE)
    return modified_content.strip()

def implement_changes(content, description, file_extension):
    # This function should be expanded to handle different types of changes
    # based on the file_extension and the description of the change
    if "add function" in description.lower():
        return add_function(content, description, file_extension)
    elif "modify function" in description.lower():
        return modify_function(content, description, file_extension)
    elif "add route" in description.lower():
        return add_route(content, description, file_extension)
    elif "add test" in description.lower():
        return add_test(content, description, file_extension)
    elif "fix bug" in description.lower():
        return fix_bug(content, description, file_extension)
    else:
        print(f"Unsupported change type in description: {description}")
        return content

def add_test(content, description, file_extension):
    if file_extension in ['.js', '.ts']:
        new_test = f"\n\ntest('{description}', async () => {{\n  // TODO: Implement test based on: {description}\n}});"
    elif file_extension == '.cs':
        new_test = f"\n\n[Fact]\npublic void {description.replace(' ', '_')}() {{\n    // TODO: Implement test based on: {description}\n}}"
    else:
        new_test = f"\n\ndef test_{description.replace(' ', '_')}():\n    # TODO: Implement test based on: {description}\n    pass"
    
    return content + new_test

def create_test_file(description, file_contents):
    # Extract the API file name from the description
    api_file_match = re.search(r"for (\w+)", description)
    if api_file_match:
        api_file_name = api_file_match.group(1)
        test_file_name = f"test_{api_file_name}.py"
        
        # Create a basic test file structure
        test_content = f"""import pytest
from {api_file_name} import app

def test_{api_file_name}_endpoints():
    # TODO: Implement test cases based on: {description}
    pass
"""
        return test_file_name, test_content
    return None

def add_function(content, description, file_extension):
    # Implement logic to add a new function based on the description and file type
    # This is a placeholder and should be expanded
    if file_extension in ['.js', '.ts']:
        new_function = f"\n\nfunction newFunction() {{\n    // TODO: Implement function based on: {description}\n}}"
    elif file_extension == '.cs':
        new_function = f"\n\npublic void NewFunction() {{\n    // TODO: Implement function based on: {description}\n}}"
    else:
        new_function = f"\n\ndef new_function():\n    # TODO: Implement function based on: {description}\n    pass"
    
    return content + new_function

def modify_function(content, description, file_extension):
    # Implement logic to modify an existing function based on the description and file type
    # This is a placeholder and should be expanded
    function_name = re.search(r"modify function (\w+)", description, re.IGNORECASE)
    if function_name:
        function_name = function_name.group(1)
        if file_extension in ['.js', '.ts']:
            pattern = rf"function {function_name}\s*\([^)]*\)\s*{{"
        elif file_extension == '.cs':
            pattern = rf"(public|private|protected)?\s+\w+\s+{function_name}\s*\([^)]*\)\s*{{"
        else:
            pattern = rf"def {function_name}\s*\([^)]*\):"
        
        modified_content = re.sub(pattern, f"\\g<0>\n    // TODO: Modify function based on: {description}", content)
        return modified_content
    return content

def add_route(content, description, file_extension):
    # Implement logic to add a new route based on the description and file type
    # This is a placeholder and should be expanded
    if file_extension in ['.js', '.ts']:
        new_route = f"\n\napp.get('/new-route', (req, res) => {{\n    // TODO: Implement route based on: {description}\n}});"
    elif file_extension == '.cs':
        new_route = f"\n\n[HttpGet(\"new-route\")]\npublic IActionResult NewRoute() {{\n    // TODO: Implement route based on: {description}\n    return Ok();\n}}"
    else:
        new_route = f"\n\n@app.route('/new-route', methods=['GET'])\ndef new_route():\n    # TODO: Implement route based on: {description}\n    return jsonify({{'message': 'New route'}})"
    
    return content + new_route

def fix_bug(content, description, file_extension):
    # Implement logic to fix a bug based on the description and file type
    # This is a placeholder and should be expanded
    return content + f"\n\n// TODO: Fix bug based on: {description}"

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

def update_readme(content, description):
    # Add a new section for running tests if it doesn't exist
    if "## Running Tests" not in content:
        content += "\n\n## Running Tests\n\nTo run the tests for this project, follow these steps:\n\n1. Ensure you have all dependencies installed.\n2. Navigate to the project root directory.\n3. Run the following command:\n\n```\npytest\n```\n\nThis will execute all the tests in the project."
    return content

def create_readme(description):
    return f"# Project Name\n\n## Description\n\nThis project is a work in progress.\n\n## Running Tests\n\nTo run the tests for this project, follow these steps:\n\n1. Ensure you have all dependencies installed.\n2. Navigate to the project root directory.\n3. Run the following command:\n\n```\npytest\n```\n\nThis will execute all the tests in the project."

# Add other issue resolution related functions here