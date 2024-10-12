from flask import Flask, request, jsonify
from dotenv import load_dotenv
from src.github_utils import setup_github_client, parse_repo_url, get_repo_issues
from src.openai_utils import setup_openai_client, plan_issue_resolution
from src.file_utils import get_local_repo_structure, save_repo_structure, get_file_content
from src.models import ResolutionPlan
from src.issue_resolution import parse_ai_response, modify_files, create_pull_request
import sys

app = Flask(__name__)

# Load environment variables and set up clients
load_dotenv()
github_client = setup_github_client()
openai_client = setup_openai_client()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/repo/issues', methods=['GET'])
def get_issues():
    repo_url = request.args.get('repo_url')
    if not repo_url:
        return jsonify({"error": "Missing repo_url parameter"}), 400

    repo_name = parse_repo_url(repo_url)
    if not repo_name:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    issues = get_repo_issues(github_client, repo_name)
    return jsonify([{"number": issue.number, "title": issue.title} for issue in issues])

@app.route('/repo/structure', methods=['GET'])
def get_structure():
    repo_url = request.args.get('repo_url')
    if not repo_url:
        return jsonify({"error": "Missing repo_url parameter"}), 400

    repo_name = parse_repo_url(repo_url)
    if not repo_name:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    structure = get_local_repo_structure(repo_name)
    if not structure:
        return jsonify({"error": "Repository structure not found locally"}), 404

    return jsonify(structure)

@app.route('/issue/plan', methods=['POST'])
def plan_resolution():
    data = request.json
    if not data or 'repo_url' not in data or 'issue_number' not in data:
        return jsonify({"error": "Missing required parameters"}), 400

    repo_name = parse_repo_url(data['repo_url'])
    if not repo_name:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    repo = github_client.get_repo(repo_name)
    try:
        issue = repo.get_issue(data['issue_number'])
    except Exception as e:
        return jsonify({"error": f"Failed to fetch issue: {str(e)}"}), 404

    relevant_files = find_relevant_files(repo, issue.title, issue.body)
    file_contents = analyze_relevant_files(repo, relevant_files)

    try:
        plan_json, token_usage = plan_issue_resolution(openai_client, issue.title, issue.body, file_contents)
        plan_dict = parse_ai_response(plan_json)
        plan = ResolutionPlan(**plan_dict)
        return jsonify({
            "plan": plan.dict(),
            "token_usage": token_usage
        })
    except Exception as e:
        return jsonify({"error": f"Failed to generate resolution plan: {str(e)}"}), 500

@app.route('/issue/resolve', methods=['POST'])
def resolve_issue():
    data = request.json
    if not data or 'repo_url' not in data or 'issue_number' not in data:
        return jsonify({"error": "Missing required parameters"}), 400

    repo_name = parse_repo_url(data['repo_url'])
    if not repo_name:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    repo = github_client.get_repo(repo_name)
    try:
        issue = repo.get_issue(data['issue_number'])
    except Exception as e:
        return jsonify({"error": f"Failed to fetch issue: {str(e)}"}), 404

    relevant_files = find_relevant_files(repo, issue.title, issue.body)
    file_contents = analyze_relevant_files(repo, relevant_files)

    try:
        plan_json, _ = plan_issue_resolution(openai_client, issue.title, issue.body, file_contents)
        plan_dict = parse_ai_response(plan_json)
        plan = ResolutionPlan(**plan_dict)
        
        modified_files = modify_files(repo, file_contents, plan)
        pr = create_pull_request(repo, issue, modified_files)
        
        if pr:
            return jsonify({
                "message": "Pull request created successfully",
                "pr_url": pr.html_url
            })
        else:
            return jsonify({"error": "Failed to create pull request"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to resolve issue: {str(e)}"}), 500

def find_relevant_files(repo, issue_title, issue_body):
    keywords = set(issue_title.lower().split() + (issue_body.lower().split() if issue_body else []))
    relevant_files = []
    contents = repo.get_contents("")
    
    def traverse_contents(contents):
        for content in contents:
            if content.type == "dir":
                traverse_contents(repo.get_contents(content.path))
            elif content.type == "file":
                file_name = content.name.lower()
                file_path = content.path.lower()
                if any(keyword in file_name or keyword in file_path for keyword in keywords):
                    relevant_files.append(content.path)
    
    traverse_contents(contents)
    
    if not relevant_files:
        traverse_contents(repo.get_contents(""))
        relevant_files = [content.path for content in contents if content.name.endswith('.py')]
    
    return relevant_files

def analyze_relevant_files(repo, relevant_files, max_file_size=100000):
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
        except Exception as e:
            print(f"Error analyzing file {file_path}: {e}")
    return file_contents

if __name__ == '__main__':
    app.run(debug=True)
