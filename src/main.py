import ssl
import os
import csv
import logging
import argparse
from dotenv import load_dotenv
from datetime import datetime
import asyncio
import aiohttp
import time

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_RECURSION_DEPTH = 5
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

async def get_github_files(session, base_url, org, filetypes, token):
    repos_url = f"{base_url}/orgs/{org}/repos"
    headers = {'Authorization': f'token {token}'}
    
    repos = []
    page = 1

    while True:
        async with session.get(repos_url, headers=headers, params={'page': page, 'per_page': 100}) as response:
            if response.status != 200:
                logging.error(f"Error fetching repositories: {response.status}")
                return []
            
            page_repos = await response.json()

        if not page_repos:
            break

        repos.extend(page_repos)
        page += 1
    
    tasks = [get_repo_contents(session, base_url, org, repo['name'], repo['default_branch'], filetypes, token) for repo in repos]
    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]

async def get_repo_contents(session, base_url, org, repo, branch, filetypes, token, path="", depth=0):
    if depth > MAX_RECURSION_DEPTH:
        return []

    contents_url = f"{base_url}/repos/{org}/{repo}/contents/{path}?ref={branch}"
    headers = {'Authorization': f'token {token}'}
    results = []

    async with session.get(contents_url, headers=headers) as response:
        if response.status != 200:
            return results
        
        contents = await response.json()

    for content in contents:
        if content['type'] == 'file' and any(content['name'].endswith(filetype) for filetype in filetypes):
            last_commit = await get_last_commit_with_retry(session, base_url, org, repo, content['path'], branch, token)
            results.append({
                'org': org,
                'repo': repo,
                'branch': branch,
                'file': content['name'],
                'file_url': content['html_url'],
                'last_committer': last_commit['name'],
                'last_committer_email': last_commit['email'],
                'last_commit_date': last_commit['date']
            })
        elif content['type'] == 'dir':
            results.extend(await get_repo_contents(session, base_url, org, repo, branch, filetypes, token, content['path'], depth+1))

    return results

async def get_last_commit_with_retry(session, base_url, org, repo, filepath, branch, token):
    for attempt in range(MAX_RETRIES):
        try:
            return await get_last_commit(session, base_url, org, repo, filepath, branch, token)
        except aiohttp.ClientResponseError as e:
            if e.status == 403:
                logging.warning(f"403 error for {repo}/{filepath}. Attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logging.error(f"Error fetching commit for {repo}/{filepath}: {e}")
                return {'name': None, 'email': None, 'date': None}
    
    logging.error(f"Failed to fetch commit for {repo}/{filepath} after {MAX_RETRIES} attempts")
    return {'name': None, 'email': None, 'date': None}

async def get_last_commit(session, base_url, org, repo, filepath, branch, token):
    commits_url = f"{base_url}/repos/{org}/{repo}/commits"
    headers = {'Authorization': f'token {token}'}
    params = {'path': filepath, 'sha': branch, 'per_page': 1}
    
    async with session.get(commits_url, headers=headers, params=params) as response:
        response.raise_for_status()
        commits = await response.json()
    
    if commits:
        commit = commits[0]['commit']
        author = commit['author']
        return {
            'name': author['name'],
            'email': author['email'],
            'date': author['date']
        }
    return {'name': None, 'email': None, 'date': None}

async def main():
    parser = argparse.ArgumentParser(description="Search for files in a GitHub organization")
    parser.add_argument("organization", help="The GitHub organization to search")
    parser.add_argument("filetypes", nargs='+', help="The file types to search for (e.g., .py .sql .sas)")
    parser.add_argument("--cert", help="Path to the certificate file for SSL verification")


    args = parser.parse_args()

    github_token = os.getenv("GITHUB_TOKEN")
    github_base_url = os.getenv("GITHUB_BASE_URL", "https://api.github.com")

    if not github_token:
        logging.error("GitHub token not found in environment variables")
        return
    # Set up SSL context
    ssl_context = ssl.create_default_context(cafile=args.cert) if args.cert else None

    conn = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=conn) as session:
        files_list = await get_github_files(session, github_base_url, args.organization, args.filetypes, github_token)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"github_files_{args.organization}_{timestamp}.csv"

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(['Organization', 'Repo', 'Branch', 'File', 'URL', 'Last Committer', 'Last Committer Email', 'Last Commit Date'])
        for file in files_list:
            writer.writerow([file['org'], file['repo'], file['branch'], file['file'], file['file_url'], 
                             file['last_committer'], file['last_committer_email'], file['last_commit_date']])

    logging.info(f"Results saved to {filename}")

if __name__ == "__main__":
    asyncio.run(main())