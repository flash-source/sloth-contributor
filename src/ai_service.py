import requests
import json
import re
from rich.console import Console

console = Console()

class AIService:
    def __init__(self, ollama_url, model_name):
        self.url = ollama_url
        self.model = model_name

    def _call_ollama(self, prompt):
        """Helper to call Ollama and return text."""
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            response = requests.post(self.url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "")
            return ""
        except Exception:
            return ""

    def suggest_files(self, title, body):
        """AI suggests which files to look at."""
        clean_body = body[:1500] if body else "No description."
        prompt = f"""Read this GitHub issue and suggest a JSON array of file paths likely causing the bug.
        Issue Title: {title}
        Issue Body: {clean_body}
        Output ONLY a JSON array of strings. Example: ["path/to/file.ext"]. If unsure, output []."""
        
        response = self._call_ollama(prompt)
        
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                json_str = match.group(0)
                files = json.loads(json_str)
                return [f for f in files if isinstance(f, str)] if isinstance(files, list) else []
            return []
        except json.JSONDecodeError:
            console.print("[dim]⚠︎ AI failed to return valid file paths. Skipping code fetch.[/dim]")
            return []

    def analyze_with_context(self, title, body, code_context):
        """AI reads the issue AND the actual code to give the final Hunch."""
        clean_body = body[:1500] if body else "No description."
        
        prompt = f"""You are an expert open-source contributor. Analyze this GitHub issue AND the provided code context to give a 'Contributor's Hunch'.
        
        Issue Title: {title}
        Issue Body: {clean_body}
        
        --- RELEVANT CODE CONTEXT ---
        {code_context}
        -----------------------------
        
        Output your response in Markdown with these exact headers:
        ### ? The Core Problem
        (1-2 sentences explaining what is actually broken)
        
        ### ☰  Where to Look
        (Reference the specific files provided in the context)
        
        ### ⚒ Suggested Fix
        (A specific, code-level strategy to solve it)
        """

        return self._call_ollama(prompt)