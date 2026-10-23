import requests
from rich.console import Console
from src.file_fetcher import FileFetcher

console = Console()

class GitHubService:
    def __init__(self, token):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
        self.fetcher = FileFetcher(token)

    def fetch_issues(self, owner, repo, labels):
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": "open",
            "sort": "created",
            "direction": "desc",
            "per_page": 10
        }

        if labels:
            params["labels"] = ",".join(labels)
            label_text = ", ".join(labels)
        else:
            label_text = "All Issues"
        
        console.print(f"[bold blue]⌯✈︎  Scanning {owner}/{repo} for {label_text}...[/bold blue]")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            # Filter out PRs
            return [issue for issue in response.json() if "pull_request" not in issue]
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error fetching from {owner}/{repo}: {e}[/red]")
            return []