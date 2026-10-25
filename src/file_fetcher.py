import requests
import base64
from rich.console import Console

console = Console()

class FileFetcher:
    def __init__(self, token):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def get_file_content(self, owner, repo, file_path):
        """Fetches the raw content of a file from GitHub."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
            
                if data.get("encoding") == "base64" and data.get("content"):
                    return base64.b64decode(data["content"]).decode("utf-8")
            else:
                console.print(f"[dim]️ Could not fetch {file_path} (Status: {response.status_code})[/dim]")
                return None
        except Exception as e:
            console.print(f"[dim]⚠︎ Error fetching {file_path}: {e}[/dim]")
            return None

    def find_file_in_tree(self, owner, repo, target_filename, branch="main"):
        """Fallback: Searches the repo's file tree to find a file by name if the exact path fails."""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                tree = response.json().get("tree", [])
                # Find a path that ends with the target filename
                for item in tree:
                    if item["path"].endswith(target_filename):
                        console.print(f"[dim] Tree fallback matched: {item['path']}[/dim]")
                        return self.get_file_content(owner, repo, item["path"])
            return None
        except Exception as e:
            console.print(f"[dim]⚠️ Tree lookup failed: {e}[/dim]")
            return None