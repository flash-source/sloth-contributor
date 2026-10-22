from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()

class SessionManager:
    def __init__(self, db):
        self.db = db
        self.sessions_collection = self.db.db["user_sessions"]

    def get_active_session(self):
        """Fetches the last active session, or prompts to create one."""
        session = self.sessions_collection.find_one({"is_active": True})
        
        if not session:
            console.print("\n[bold yellow]ωᥱℓᥴ𐐫mᥱ!༄˖°.🍂.ೃ࿔*:･🎃[/bold yellow]")
            console.print("[dim]Let's set up your first watching session.[/dim]\n")
            return self.create_new_session()
        
        console.print(f"\n[bold green]▶ Resumed Session:[/bold green] [cyan]{session['owner']}/{session['name']}[/cyan] (Labels: {', '.join(session['labels'])})")
        if Confirm.ask("Use this session?", default=True):
            return session
        
        return self.create_new_session()

    def create_new_session(self):
        """Interactively creates a new watching session."""
        console.print("\n[bold]✚ Create New Watching Session[/bold]")
        
        owner = Prompt.ask("GitHub Repo Owner (e.g., 'vercel', 'facebook')")
        name = Prompt.ask("Repository Name (e.g., 'next.js', 'react')")
        
        labels_input = Prompt.ask(
            "Labels to watch (comma-separated, e.g., 'good first issue, help wanted')",
            default="good first issue"
        )
        labels = [label.strip() for label in labels_input.split(",") if label.strip()]
       
        self.sessions_collection.update_many({}, {"$set": {"is_active": False}})
        
        new_session = {
            "owner": owner,
            "name": name,
            "labels": labels,
            "is_active": True
        }
        self.sessions_collection.insert_one(new_session)
        
        console.print(f"[bold green]✔ Session saved: {owner}/{name}[/bold green]\n")
        return new_session

    def list_sessions(self):
        """Lists all saved sessions and lets the user switch."""
        sessions = list(self.sessions_collection.find({}))
        if not sessions:
            console.print("[yellow]No saved sessions.[/yellow]")
            return None
            
        console.print("\n[bold]🗐 Saved Sessions:[/bold]")
        for i, session in enumerate(sessions):
            status = "[bold green](Active)[/bold green]" if session.get("is_active") else "[dim](Inactive)[/dim]"
            console.print(f"{i+1}. {session['owner']}/{session['name']} - Labels: {', '.join(session['labels'])} {status}")
            
        choice = Prompt.ask("Enter number to switch session, or '0' to create new", default="0")
        
        if choice == "0":
            return self.create_new_session()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                self.sessions_collection.update_many({}, {"$set": {"is_active": False}})
                self.sessions_collection.update_one({"_id": sessions[idx]["_id"]}, {"$set": {"is_active": True}})
                console.print(f"[bold green]✔ Switched to: {sessions[idx]['owner']}/{sessions[idx]['name']}[/bold green]\n")
                return sessions[idx]
        except ValueError:
            pass
            
        console.print("[red]Invalid choice.[/red]")
        return None