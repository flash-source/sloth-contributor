import time
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from src.config import get_env_vars
from src.database import Database
from src.github_service import GitHubService
from src.ai_service import AIService
from src.notifier import send_desktop_notification
from src.session_manager import SessionManager

console = Console()

def run_scan_for_session(session, db, github, ai):
    """Runs a scan for a specific session."""
    owner = session["owner"]
    name = session["name"]
    labels = session["labels"]
    
    console.print(f"\n[bold blue]ᯤ Scanning {owner}/{name} for {labels}...[/bold blue]")
    issues = github.fetch_issues(owner, name, labels)
    
    new_issues_found = 0
    for issue in issues:
        if db.is_issue_analyzed(issue["id"]):
            continue
        
        console.print(f"\n[bold cyan]ᝰ.ᐟ NEW Sniped Issue: {issue['title']}[/bold cyan]")
        console.print(f"[dim]Link: {issue['html_url']}[/dim]")
        
        suggested_files = ai.suggest_files(issue["title"], issue.get("body", ""))
        code_context = "No specific code context fetched."
        
        if suggested_files:
            console.print(f"[dim]🔍︎ AI suggested checking: {suggested_files}[/dim]")
            fetched_codes = []
            for file_path in suggested_files[:3]:
                content = github.fetcher.get_file_content(owner, name, file_path)
                if content:
                    fetched_codes.append(f"--- FILE: {file_path} ---\n{content[:1000]}...") # Truncate for prompt limits
            
            if fetched_codes:
                code_context = "\n\n".join(fetched_codes)
        
        hunch = ai.analyze_with_context(issue["title"], issue.get("body", ""), code_context)
        console.print(Panel(Markdown(hunch), title="Contributor's Hunch (Code-Aware)", border_style="bright_magenta"))
        
        issue["repo"] = f"{owner}/{name}"
        db.save_issue(issue, hunch)
        
        send_desktop_notification(
            title=f"𖦏 New Issue: {owner}/{name}",
            message=f"{issue['title'][:40]}..."
        )
        new_issues_found += 1
        time.sleep(2)
        
    console.print(f"\n[bold]✔ Scan Complete: Found {new_issues_found} new issues.[/bold]")

def main():
    env = get_env_vars()
    db = Database(env["mongo_uri"])
    github = GitHubService(env["github_token"])
    ai = AIService(env["ollama_url"], env["model_name"])
    session_mgr = SessionManager(db)
    
    console.print(Panel.fit("[bold green]꩜ SlothContributor ꩜[/bold green]\nLocal AI OSS Issue Sniper", border_style="green"))
    
    # Interactive Session Selection
    active_session = session_mgr.get_active_session()
    if not active_session:
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Continuous watch mode")
    args = parser.parse_args()
    
    if args.watch:
        interval = 15 * 60 # 15 minutes
        console.print(f"[bold yellow]⏲ Watch mode active. Polling every 15 mins. Press Ctrl+C to stop.[/bold yellow]")
        try:
            while True:
                run_scan_for_session(active_session, db, github, ai)
                console.print(f"[dim]ᶻ𝗓𐰁 Sleeping...[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⏻ Watch mode stopped.[/bold yellow]")
    else:
        run_scan_for_session(active_session, db, github, ai)
        
        while True:
            action = Prompt.ask("\n[bold]Next Action?[/bold] [1] Switch Session, [2] Scan Again, [3] Exit", choices=["1", "2", "3"], default="3")
            if action == "1":
                active_session = session_mgr.list_sessions() or active_session
            elif action == "2":
                run_scan_for_session(active_session, db, github, ai)
            else:
                console.print("[bold green]Stay lazy, contribute smartly! 🦥[/bold green]")
                break

if __name__ == "__main__":
    main()