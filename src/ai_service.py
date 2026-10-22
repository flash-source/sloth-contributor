import requests
from rich.console import Console

console = Console()

class AIService:
    def __init__(self, ollama_url, model_name):
        self.url = ollama_url
        self.model = model_name

    def analyze_issue(self, title, body):
        console.print(f"[dim]🧠 Asking local {self.model} to analyze...[/dim]")
        
        # Truncate body to avoid token limits
        clean_body = body[:2000] if body else "No description provided."
        
        prompt = f"""You are an expert open-source contributor. Analyze this GitHub issue and provide a 'Contributor's Hunch'.
        Issue Title: {title}
        Issue Body: {clean_body}
        
        Output your response in Markdown with these exact headers:
        ### 🎯 The Core Problem
        (1-2 sentences explaining what is actually broken)
        
        ### 📂 Where to Look
        (Suggest which files or parts of the codebase they should check first)
        
        ### 🛠️ Suggested Fix
        (A brief, lazy-friendly strategy to solve it)
        """

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        
        try:
            response = requests.post(self.url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "No response generated.")
            else:
                return f"Error calling Ollama: {response.text}"
        except Exception as e:
            return f"Failed to connect to Ollama. Is it running? Error: {e}"