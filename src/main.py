import os
import requests
import csv
import logging
import argparse
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_github_files(org, filetypes, token):
    repos_url = f"https://api.github.com/orgs/{org}/repos"
    headers = {'Authorization': f'token {token}'}
    
    repos = []
    page = 1

    while True:
        response = requests.get(repos_url, headers=headers, params={'page': page, 'per_page': 100})
        if response.status_code != 200:
            logging.error(f"Error fetching repositories: {response.status_code}")
            logging.error(response.json())
            return []
        
        page_repos = response.json()
        logging.info(f"Fetched page {page} of repositories")

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
            logging.error(f"Error fetching contents for {repo_name}: {contents_response.status_code}")
            continue
        
        contents = contents_response.json()

        for content in contents:
            if content['type'] == 'file' and any(content['name'].endswith(filetype) for filetype in filetypes):
                committer_info = get_last_committer(org, repo_name, content['path'], token)
                file_info = {
                    'org': org,
                    'repo': repo_name,
                    'file': content['name'],
                    'file_url': content['html_url'],
                    'last_committer': committer_info['name'],
                    'last_committer_email': committer_info['email']
                }
                results.append(file_info)
    
    return results

def get_last_committer(org, repo, filepath, token):
    commits_url = f"https://api.github.com/repos/{org}/{repo}/commits?path={filepath}"
    headers = {'Authorization': f'token {token}'}
    
    commits_response = requests.get(commits_url, headers=headers)
    if commits_response.status_code != 200:
        logging.error(f"Error fetching commits for {repo}/{filepath}: {commits_response.status_code}")
        return {'name': None, 'email': None}
    
    commits = commits_response.json()
    
    if commits:
        commit_author = commits[0]['commit']['author']
        return {'name': commit_author['name'], 'email': commit_author.get('email')}
    return {'name': None, 'email': None}

def main():
    parser = argparse.ArgumentParser(description="Search for files in a GitHub organization")
    parser.add_argument("organization", help="The GitHub organization to search")
    parser.add_argument("filetypes", nargs='+', help="The file types to search for (e.g., .py .sql .sas)")

    args = parser.parse_args()

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logging.error("GitHub token not found in environment variables")
        return

    # Get list of files
    files_list = get_github_files(args.organization, args.filetypes, github_token)

    # Get current timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"github_files_{args.organization}_{timestamp}.csv"

    # Write results to a CSV file
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(['Organization', 'Repo', 'File', 'URL', 'Last Committer', 'Last Committer Email'])
        for file in files_list:
            writer.writerow([file['org'], file['repo'], file['file'], file['file_url'], file['last_committer'], file['last_committer_email']])

    logging.info(f"Results saved to {filename}")

if __name__ == "__main__":
    main()
