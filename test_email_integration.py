#!/usr/bin/env python3
"""Test script to verify email integration in TaskService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.task_service import TaskService
from app.adapters.email.base import EmailSender
from app.db.models import User
from sqlalchemy.orm import Session


class MockEmailSender(EmailSender):
    def __init__(self):
        self.sent_emails = []
    
    async def send(self, to_email: str, subject: str, body_text: str) -> None:
        self.sent_emails.append({
            "to": to_email,
            "subject": subject,
            "body": body_text
        })


class MockSession(Session):
    def __init__(self):
        pass
    
    def get(self, entity, ident):
        if entity.__name__ == "Counter" and ident == "task":
            counter = MagicMock()
            counter.value = 0
            return counter
        return None
    
    def add(self, obj):
        pass
    
    def commit(self):
        pass


class MockGateway:
    async def create_task_page(self, props):
        # Return a mock page that parses to a task
        # Extract title from props - it's stored in "Task name" property
        title = "Untitled Task"
        if "Task name" in props and "title" in props["Task name"] and len(props["Task name"]["title"]) > 0:
            title = props["Task name"]["title"][0]["text"]["content"]
        
        return {
            "id": "mock_page_id",
            "properties": {
                "Task name": {"title": [{"text": {"content": title}}]},
                "Task ID (system)": {"rich_text": [{"text": {"content": "TSK-0001"}}]},
                "Due date": {"date": {"start": props.get("deadline")}} if props.get("deadline") else {},
                "Description": {"rich_text": [{"text": {"content": props.get("description", "")}}]} if props.get("description") else {},
                "Status": {"status": {"name": props.get("status", "Not started")}}
            }
        }
    
    async def update_task_page(self, page_id, props):
        # For reassignment, we need to return a page with updated assignee info
        # Extract title from props
        title = "Untitled Task"
        if "Task name" in props and "title" in props["Task name"] and len(props["Task name"]["title"]) > 0:
            title = props["Task name"]["title"][0]["text"]["content"]
        
        return {
            "id": "mock_page_id",
            "properties": {
                "Task name": {"title": [{"text": {"content": title}}]},
                "Task ID (system)": {"rich_text": [{"text": {"content": "TSK-0001"}}]},
                "Due date": {"date": {"start": None}},  # No deadline in reassignment props
                "Description": {"rich_text": [{"text": {"content": ""}}]},  # Empty description
                "Status": {"status": {"name": "Not started"}}
            }
        }
    
    def parse_task(self, page):
        return {
            "page_id": page["id"],
            "task_id": page["properties"]["Task ID (system)"]["rich_text"][0]["text"]["content"],
            "title": page["properties"]["Task name"]["title"][0]["text"]["content"],
            "deadline": page["properties"].get("Due date", {}).get("date", {}).get("start"),
            "description": page["properties"].get("Description", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
            "status": page["properties"]["Status"]["status"]["name"]
        }


async def test_task_creation_email():
    """Test that creating a task sends assignment emails."""
    print("Testing task creation email...")
    
    # Setup mocks
    email_sender = MockEmailSender()
    gateway = MockGateway()
    session = MockSession()
    
    # Create task service
    task_service = TaskService(gateway, session, email_sender)
    
    # Create assignee users
    assignee1 = User(
        email="test1@example.com",
        display_name="Test User 1",
        notion_user_id="notion_id_1",
        active=True
    )
    assignee2 = User(
        email="test2@example.com", 
        display_name="Test User 2",
        notion_user_id="notion_id_2",
        active=True
    )
    
    # Create task
    task = await task_service.create_task(
        actor_name="Test Actor",
        title="Test Task for Email",
        assignee_users=[assignee1, assignee2],
        deadline="2026-12-31",
        description="This is a test task to verify email functionality",
        priority="High"
    )
    
    # Verify task was created
    assert task["title"] == "Test Task for Email"
    assert task["task_id"] == "TSK-0001"
    print(f"[+] Task created: {task['title']} (ID: {task['task_id']})")
    
    # Verify emails were sent
    assert len(email_sender.sent_emails) == 2
    print(f"[+] {len(email_sender.sent_emails)} assignment emails sent")
    
    # Verify email content
    for i, email in enumerate(email_sender.sent_emails):
        assert email["to"] in ["test1@example.com", "test2@example.com"]
        assert "[SEE Notion] Bạn đã được gán task:" in email["subject"]
        assert "Test Task for Email" in email["body"]
        assert "TSK-0001" in email["body"]
        print(f"[+] Email {i+1} to {email['to']} verified")
    
    return True


async def test_task_reassign_email():
    """Test that reassigning a task sends notification emails."""
    print("\nTesting task reassignment email...")
    
    # Setup mocks
    email_sender = MockEmailSender()
    gateway = MockGateway()
    session = MockSession()
    
    # Create task service
    task_service = TaskService(gateway, session, email_sender)
    
    # First create a task
    task = await task_service.create_task(
        actor_name="Test Actor",
        title="Task to Reassign",
        assignee_users=[],  # No initial assignees
        deadline="2026-12-31",
        description="Task to be reassigned"
    )
    
    print(f"[+] Initial task created: {task['title']}")
    
    # Create new assignees
    new_assignee1 = User(
        email="new1@example.com",
        display_name="New User 1",
        notion_user_id="notion_id_3",
        active=True
    )
    new_assignee2 = User(
        email="new2@example.com",
        display_name="New User 2", 
        notion_user_id="notion_id_4",
        active=True
    )
    
    # Reassign task
    updated_task = await task_service.reassign(
        actor_name="Test Actor",
        task=task,
        new_assignees=[new_assignee1, new_assignee2]
    )
    
    # Verify task was updated
    assert updated_task["title"] == "Task to Reassign"
    print(f"[+] Task reassigned: {updated_task['title']}")
    
    # Verify emails were sent (should be 2 new emails)
    assert len(email_sender.sent_emails) == 2
    print(f"[+] {len(email_sender.sent_emails)} reassignment emails sent")
    
    # Verify email content
    for i, email in enumerate(email_sender.sent_emails):
        assert email["to"] in ["new1@example.com", "new2@example.com"]
        assert "[SEE Notion] Bạn đã được gán lại task:" in email["subject"]
        assert "Task to Reassign" in email["body"]
        assert "TSK-0001" in email["body"]
        print(f"[+] Reassignment email {i+1} to {email['to']} verified")
    
    return True


async def main():
    """Run all tests."""
    print("=== Testing Email Integration in TaskService ===\n")
    
    try:
        await test_task_creation_email()
        await test_task_reassign_email()
        print("\n[+] All tests passed!")
        return True
    except Exception as e:
        print(f"\n[-] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)