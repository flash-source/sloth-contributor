import requests
import base64
from rich.console import Console

console = Console()

class FileFetcher:
    def __init__(self, github_token):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
        
        self._tree_cache = {} 

    def get_file_content(self, owner, repo, file_path, branch="main"):
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

    def find_file_in_tree(self, owner, repo, target_path, branch="HEAD"):
        """Fallback: Searches the repo's file tree to find a file by path/name if the exact path fails."""
        cache_key = f"{owner}/{repo}"

        if cache_key not in self._tree_cache:
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("truncated"):
                        console.print(f"[dim]⚠︎ Tree truncated for {owner}/{repo}. Fallback may miss files.[/dim]")
                    self._tree_cache[cache_key] = data.get("tree", [])
                else:
                    self._tree_cache[cache_key] = []
            except Exception as e:
                console.print(f"[dim]⚠︎ Tree lookup failed: {e}[/dim]")
                return None

        tree = self._tree_cache[cache_key]
        if not tree:
            return None

        wanted = target_path.strip("/").split("/")
        best, best_score = None, 0

        for item in tree:
            if item.get("type") != "blob":
                continue

            parts = item["path"].split("/")
            if parts[-1] != wanted[-1]:
                continue

            score = 0
            for a, b in zip(reversed(parts), reversed(wanted)):
                if a != b:
                    break
                score += 1

            if score > best_score:
                best, best_score = item["path"], score

        if best:
            console.print(f"[dim]Tree fallback matched: {best} (score: {best_score})[/dim]")
            return best, self.get_file_content(owner, repo, best)

        return None

        