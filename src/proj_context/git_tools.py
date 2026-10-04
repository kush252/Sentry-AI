import os
import re
import requests
import base64
from typing import Dict, List, Optional, Any

class GitHubAPIClient:
    """
    A client to interact with the GitHub REST API.
    Provides tools to extract repository context without cloning the project.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Extract owner and repo name from a GitHub URL.
        Example: https://github.com/octocat/Hello-World -> ('octocat', 'Hello-World')
        """
        # Handle formats: https://github.com/owner/repo or owner/repo
        match = re.search(r"github\.com/([^/]+)/([^/.]+)", repo_url)
        if match:
            return match.group(1), match.group(2)
            
        parts = repo_url.strip("/").split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
            
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    # --- Repository Tools ---

    def get_repository_metadata(self, repo_url: str) -> Dict[str, Any]:
        """Get general repository metadata (description, language, stars, etc.)."""
        owner, repo = self._parse_repo_url(repo_url)
        return self._get(f"/repos/{owner}/{repo}")

    def get_branches(self, repo_url: str) -> List[Dict[str, Any]]:
        """List all branches in the repository."""
        owner, repo = self._parse_repo_url(repo_url)
        return self._get(f"/repos/{owner}/{repo}/branches")

    # --- Commit Tools ---

    def get_commit_history(self, repo_url: str, branch_or_sha: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Get the commit history for a repository or specific branch."""
        owner, repo = self._parse_repo_url(repo_url)
        params = {"per_page": limit}
        if branch_or_sha:
            params["sha"] = branch_or_sha
        return self._get(f"/repos/{owner}/{repo}/commits", params=params)

    def get_commit(self, repo_url: str, commit_sha: str) -> Dict[str, Any]:
        """Get detailed information about a specific commit, including file changes."""
        owner, repo = self._parse_repo_url(repo_url)
        return self._get(f"/repos/{owner}/{repo}/commits/{commit_sha}")

    def get_commit_differences(self, repo_url: str, base: str, head: str) -> Dict[str, Any]:
        """
        Compare two commits or branches.
        base: The starting point (e.g., 'main')
        head: The end point (e.g., 'feature-branch' or commit SHA)
        """
        owner, repo = self._parse_repo_url(repo_url)
        return self._get(f"/repos/{owner}/{repo}/compare/{base}...{head}")

    # --- File & Tree Tools ---

    def get_git_tree(self, repo_url: str, tree_sha: str = "HEAD", recursive: bool = True) -> Dict[str, Any]:
        """
        Get the git tree (directory structure) for a given branch or commit SHA.
        If recursive is True, returns all files in all subdirectories.
        """
        owner, repo = self._parse_repo_url(repo_url)
        endpoint = f"/repos/{owner}/{repo}/git/trees/{tree_sha}"
        params = {"recursive": "1"} if recursive else {}
        return self._get(endpoint, params=params)

    def get_file_content(self, repo_url: str, file_path: str, ref: Optional[str] = None) -> str:
        """
        Get the raw content of an individual file.
        ref: The branch, tag, or commit SHA. Defaults to the default branch.
        """
        owner, repo = self._parse_repo_url(repo_url)
        params = {"ref": ref} if ref else {}
        data = self._get(f"/repos/{owner}/{repo}/contents/{file_path}", params=params)
        
        if isinstance(data, list):
            raise ValueError(f"Path '{file_path}' is a directory, not a file.")
            
        if data.get("encoding") == "base64":
            decoded_bytes = base64.b64decode(data["content"])
            return decoded_bytes.decode("utf-8")
        else:
            # For large files, github might not return base64 inline, but provide a download_url
            download_url = data.get("download_url")
            if download_url:
                resp = requests.get(download_url)
                resp.raise_for_status()
                return resp.text
            return data.get("content", "")

    def get_readme(self, repo_url: str, ref: Optional[str] = None) -> str:
        """Get the README file content."""
        owner, repo = self._parse_repo_url(repo_url)
        params = {"ref": ref} if ref else {}
        try:
            data = self._get(f"/repos/{owner}/{repo}/readme", params=params)
            if data.get("encoding") == "base64":
                decoded_bytes = base64.b64decode(data["content"])
                return decoded_bytes.decode("utf-8")
            return data.get("content", "")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return "README not found."
            raise

    # --- Pull Request Tools ---

    def get_pull_requests(self, repo_url: str, state: str = "open", limit: int = 30) -> List[Dict[str, Any]]:
        """
        Get pull requests for the repository.
        state: 'open', 'closed', or 'all'
        """
        owner, repo = self._parse_repo_url(repo_url)
        params = {"state": state, "per_page": limit}
        return self._get(f"/repos/{owner}/{repo}/pulls", params=params)


# --- Convenience Wrappers (Tools) ---

def extract_project_context(repo_url: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    A comprehensive tool that gathers the most critical project context in one call:
    Metadata, README, default branch structure, and recent commits.
    """
    client = GitHubAPIClient(token=github_token)
    
    try:
        # 1. Repo Metadata
        meta = client.get_repository_metadata(repo_url)
        default_branch = meta.get("default_branch", "main")
        
        # 2. README
        readme = client.get_readme(repo_url, ref=default_branch)
        
        # 3. Top-level tree
        tree = client.get_git_tree(repo_url, tree_sha=default_branch, recursive=False)
        top_level_files = [item["path"] for item in tree.get("tree", [])]
        
        # 4. Recent commits
        commits = client.get_commit_history(repo_url, branch_or_sha=default_branch, limit=5)
        recent_commits = [
            {"sha": c["sha"], "message": c["commit"]["message"], "author": c["commit"]["author"]["name"]}
            for c in commits
        ]
        
        return {
            "metadata": {
                "name": meta.get("name"),
                "full_name": meta.get("full_name"),
                "description": meta.get("description"),
                "language": meta.get("language"),
                "default_branch": default_branch
            },
            "top_level_files": top_level_files,
            "recent_commits": recent_commits,
            "readme_preview": readme[:500] + "..." if len(readme) > 500 else readme
        }
    except Exception as e:
        return {"error": str(e)}
