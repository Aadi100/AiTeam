"""
DevSquad Database Initialization & Seeding with MongoEngine
Connects to local MongoDB at mongodb://localhost:27017/devsquad and seeds
the dedicated team: Michael (Frontend Specialist), Dave (Backend Specialist), and Sarah (QA/UX).
"""

import os
import mongoengine as me
from dotenv import load_dotenv
from models import (
    AgentDocument,
    TaskDocument,
    TrainingPairDocument,
    CustomModelDocument,
    MessageDocument,
    ProjectStateDocument,
    ResearchBriefDocument
)

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/devsquad')


def init_db(app=None):
    """Initialize MongoEngine connection to local MongoDB."""
    try:
        connection = me.connect(host=MONGO_URI, alias='default', serverSelectionTimeoutMS=3000)
        print(f"[OK] Connected to MongoDB via MongoEngine: {MONGO_URI}")
        seed_initial_data()
        return connection
    except Exception as e:
        print(f"[WARN] Could not connect to MongoDB at {MONGO_URI}: {e}")
        return None


def seed_initial_data():
    """Seed initial agent team (Michael for Frontend, Dave for Backend) if database is empty."""
    # 1. Seed Team Members
    if AgentDocument.objects.count() == 0:
        print("[INFO] Seeding default team: Michael (Frontend) & Dave (Backend) into MongoDB...")
        initial_agents = [
            {
                'agent_id': 'michael',
                'name': 'Michael',
                'role': 'Frontend Specialist',
                'department': 'Frontend',
                'avatar': '💻',
                'color': 'from-cyan-500 to-blue-600',
                'status': 'idle',
                'status_text': 'Orbital Frontend Station online. Standing by for directives.',
                'model': 'gemini-2.0-flash',
                'system_prompt': 'You are Michael, Senior Frontend Developer. You build responsive, modern, beautiful user interfaces using HTML5, CSS3, Tailwind CSS, JavaScript, and React.',
                'skills': ['HTML5 & Modern CSS', 'Tailwind CSS', 'JavaScript (ESNext)', 'React Components', 'UI/UX & Responsive Design'],
                'stats': {'tasksDone': 12, 'filesCreated': 18, 'reviewsDone': 10},
                'desk': {'room': 'Orbital Station Alpha', 'col': 1, 'row': 1}
            },
            {
                'agent_id': 'dave',
                'name': 'Dave',
                'role': 'Backend Specialist',
                'department': 'Backend',
                'avatar': '⚙️',
                'color': 'from-emerald-500 to-teal-700',
                'status': 'idle',
                'status_text': 'Orbital Backend Station online. Database handlers synced.',
                'model': 'gemini-2.0-flash',
                'system_prompt': 'You are Dave, Senior Backend Developer. You build robust REST APIs, Flask/Node.js servers, database schemas, and server-side logic.',
                'skills': ['Python Flask', 'Node.js & Express', 'MongoDB & SQLite', 'REST API Architecture', 'Authentication & Endpoints'],
                'stats': {'tasksDone': 14, 'filesCreated': 16, 'reviewsDone': 12},
                'desk': {'room': 'Orbital Station Beta', 'col': 2, 'row': 1}
            },
            {
                'agent_id': 'sarah',
                'name': 'Sarah',
                'role': 'QA & UI/UX Specialist',
                'department': 'Design & QA',
                'avatar': '🎨',
                'color': 'from-purple-500 to-pink-600',
                'status': 'idle',
                'status_text': 'Quality control matrix primed.',
                'model': 'gemini-2.0-flash',
                'system_prompt': 'You are Sarah, QA & Design Specialist. You verify UI styling, responsiveness, cross-browser compatibility, and API integrity.',
                'skills': ['UI/UX Testing', 'Responsiveness QA', 'API Validation', 'Accessibility'],
                'stats': {'tasksDone': 8, 'filesCreated': 6, 'reviewsDone': 15},
                'desk': {'room': 'Orbital Station Gamma', 'col': 3, 'row': 1}
            }
        ]

        for agent_data in initial_agents:
            AgentDocument(**agent_data).save()
        print(f"[OK] Successfully seeded {len(initial_agents)} team members into MongoDB.")

    # 2. Seed Initial Project State
    if ProjectStateDocument.objects.count() == 0:
        ProjectStateDocument(
            singleton_id='current_project',
            project_name='Mission Control Office',
            project_goal='Standing by for user voice/chat directive to build in parallel...',
            status='idle',
            progress=0
        ).save()
