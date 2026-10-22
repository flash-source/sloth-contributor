import time
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.config import get_env_vars, load_config
from src.database import Database
from src.github_service import GitHubService
from src.ai_service import AIService
from src.notifier import send_desktop_notification

console = Console()

def run_single_scan():
    """Runs a single scan of all configured repositories."""
    env = get_env_vars()
    config = load_config()
    
    db = Database(env["mongo_uri"])
    github = GitHubService(env["github_token"])
    ai = AIService(env["ollama_url"], env["model_name"])
    
    console.print(Panel.fit("[bold green]SlothContributor: Single Scan[/bold green]", border_style="green"))
    
    new_issues_found = 0
    
    for repo_config in config["repos"]:
        owner = repo_config["owner"]
        name = repo_config["name"]
        labels = repo_config["labels"]
        
        issues = github.fetch_issues(owner, name, labels)
        
        for issue in issues:
            if db.is_issue_analyzed(issue["id"]):
                continue 
            
            console.print(f"\n[bold cyan]📌 NEW Sniped Issue: {issue['title']}[/bold cyan]")
            console.print(f"[dim]Repo: {owner}/{name} | Link: {issue['html_url']}[/dim]")
        
            hunch = ai.analyze_issue(issue["title"], issue.get("body", ""))
            console.print(Panel(Markdown(hunch), title="Contributor's Hunch", border_style="bright_magenta"))

            issue["repo"] = f"{owner}/{name}"
            db.save_issue(issue, hunch)
            
            send_desktop_notification(
                title=f"🎯 New Issue: {owner}/{name}",
                message=f"{issue['title'][:50]}...\nCheck terminal for AI Hunch!"
            )
            
            new_issues_found += 1
            time.sleep(1) 
            
    console.print(f"\n[bold]✅ Scan Complete: Found and analyzed {new_issues_found} new issues.[/bold]")

def run_watch_mode():
    """Runs continuously in the background, polling at configured intervals."""
    config = load_config()
    interval = config.get("poll_interval_minutes", 15) * 60
    
    console.print(Panel.fit(
        f"[bold green]SlothContributor: Watch Mode Active[/bold green]\n"
        f"Polling every {interval//60} minutes. Press Ctrl+C to stop.", 
        border_style="green"
    ))
    
    try:
        while True:
            run_single_scan()
            console.print(f"[dim]💤 Sleeping for {interval//60} minutes...[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Watch mode stopped. Stay lazy, contribute smartly![/bold yellow]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SlothContributor: Local AI OSS Issue Sniper")
    parser.add_argument("--watch", action="store_true", help="Run in continuous background watch mode")
    args = parser.parse_args()
    
    if args.watch:
        run_watch_mode()
    else:
        run_single_scan()