from pymongo import MongoClient
from datetime import datetime, timezone

class Database:
    def __init__(self, mongo_uri):
        self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self.db = self.client["sloth_contributor"]
        self.issues_collection = self.db["sniped_issues"]
        self._test_connection()

    def _test_connection(self):
        self.client.admin.command('ping')
        print("Successfully connected to MongoDB Atlas!")

    def is_issue_analyzed(self, issue_id):
        return self.issues_collection.find_one({"issue_id": issue_id}) is not None

    def save_issue(self, issue_data, hunch):
        document = {
            "issue_id": issue_data["id"],
            "title": issue_data["title"],
            "url": issue_data["html_url"],
            "repo": issue_data["repo"],
            "labels": [label["name"] for label in issue_data.get("labels", [])],
            "hunch": hunch,
            "analyzed_at": datetime.now(timezone.utc)
        }
        self.issues_collection.insert_one(document)
        print(f"Saved '{issue_data['title']}' to MongoDB.")