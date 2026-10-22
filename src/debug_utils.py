from rich.console import Console
import requests

console = Console()

def test_github_api(owner, repo, labels, token):
    """Debug function to test GitHub API directly."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {
        "labels": ",".join(labels),
        "state": "open",
        "sort": "created",
        "direction": "desc",
        "per_page": 5
    }
    
    console.print(f"[bold blue]Testing API: {url}[/bold blue]")
    console.print(f"[dim]Params: {params}[/dim]")
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    console.print(f"[bold]Status Code: {response.status_code}[/bold]")
    
    if response.status_code == 200:
        issues = response.json()
        # Filter out PRs
        issues = [i for i in issues if "pull_request" not in i]
        console.print(f"[bold green]Found {len(issues)} issues![/bold green]")
        
        for i, issue in enumerate(issues[:3], 1):
            console.print(f"\n[bold cyan]{i}. {issue['title']}[/bold cyan]")
            console.print(f"[dim]Labels: {[l['name'] for l in issue.get('labels', [])]}[/dim]")
            console.print(f"[dim]ID: {issue['id']}[/dim]")
    else:
        console.print(f"[bold red]Error: {response.text}[/bold red]")
    
    return response.status_code