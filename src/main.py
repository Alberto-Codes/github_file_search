import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_github_files(org, filetype, token):
    repos_url = f"https://api.github.com/orgs/{org}/repos"
    headers = {'Authorization': f'token {token}'}
    
    repos = []
    page = 1

    while True:
        response = requests.get(repos_url, headers=headers, params={'page': page, 'per_page': 100})
        if response.status_code != 200:
            print(f"Error fetching repositories: {response.status_code}")
            print(response.json())
            return []
        
        page_repos = response.json()
        print(f"Page {page} response: {page_repos}")  # Added logging

        if not page_repos:
            break

        repos.extend(page_repos)
        page += 1
    
    results = []
    
    for repo in repos:
        repo_name = repo['name']
        contents_url = f"https://api.github.com/repos/{org}/{repo_name}/contents"
        
        contents_response = requests.get(contents_url, headers=headers)
        if contents_response.status_code != 200:
            print(f"Error fetching contents for {repo_name}: {contents_response.status_code}")
            continue
        
        contents = contents_response.json()
        print(f"Contents of {repo_name}: {contents}")  # Added logging

        for content in contents:
            if content['type'] == 'file' and content['name'].endswith(filetype):
                file_info = {
                    'repo': repo_name,
                    'file': content['name'],
                    'file_url': content['html_url'],
                    'last_committer': get_last_committer(org, repo_name, content['path'], token)
                }
                results.append(file_info)
    
    return results

def get_last_committer(org, repo, filepath, token):
    commits_url = f"https://api.github.com/repos/{org}/{repo}/commits?path={filepath}"
    headers = {'Authorization': f'token {token}'}
    
    commits_response = requests.get(commits_url, headers=headers)
    if commits_response.status_code != 200:
        print(f"Error fetching commits for {repo}/{filepath}: {commits_response.status_code}")
        return None
    
    commits = commits_response.json()
    print(f"Commits for {repo}/{filepath}: {commits}")  # Added logging
    
    if commits:
        return commits[0]['commit']['author']['name']
    return None

# Load variables from environment
organization = os.getenv("GITHUB_ORG")
file_type = os.getenv("GITHUB_FILE_TYPE")
github_token = os.getenv("GITHUB_TOKEN")

# Get list of files
files_list = get_github_files(organization, file_type, github_token)

for file in files_list:
    print(f"Repo: {file['repo']}, File: {file['file']}, URL: {file['file_url']}, Last Committer: {file['last_committer']}")
