"""
DevSquad Clean Reset Script
Cleans existing agents and collections, and initializes the clean team:
- Michael (Frontend Specialist)
- Dave (Backend Specialist)
- Sarah (QA & UI Designer)
"""

import mongoengine as me
from models import AgentDocument, TaskDocument, ProjectStateDocument, MessageDocument

MONGO_URI = 'mongodb://localhost:27017/devsquad'

def reset():
    me.connect(host=MONGO_URI, alias='default', serverSelectionTimeoutMS=3000)
    print("[INFO] Connected to MongoDB. Clearing old data...")

    AgentDocument.objects.delete()
    TaskDocument.objects.delete()
    ProjectStateDocument.objects.delete()
    MessageDocument.objects.delete()

    print("[INFO] Seeding clean team: Michael (Frontend) & Dave (Backend)...")

    michael = AgentDocument(
        agent_id='michael',
        name='Michael',
        role='Frontend Specialist',
        department='Frontend',
        avatar='💻',
        color='from-cyan-500 to-blue-600',
        status='idle',
        status_text='Orbital Frontend Station online. Standing by for directives.',
        model='gemini-2.0-flash',
        system_prompt='You are Michael, Senior Frontend Developer. You build responsive, modern, beautiful user interfaces using HTML5, CSS3, Tailwind CSS, JavaScript, and React.',
        skills=['HTML5 & Modern CSS', 'Tailwind CSS', 'JavaScript (ESNext)', 'React Components', 'UI/UX & Responsive Design'],
        stats={'tasksDone': 0, 'filesCreated': 0, 'reviewsDone': 0},
        desk={'room': 'Orbital Station Alpha', 'col': 1, 'row': 1}
    ).save()

    dave = AgentDocument(
        agent_id='dave',
        name='Dave',
        role='Backend Specialist',
        department='Backend',
        avatar='⚙️',
        color='from-emerald-500 to-teal-700',
        status='idle',
        status_text='Orbital Backend Station online. Database handlers synced.',
        model='claude-3-5-sonnet',
        system_prompt='You are Dave, Senior Backend Developer. You build robust REST APIs, Flask/Node.js servers, database schemas, and server-side logic.',
        skills=['Python Flask', 'Node.js & Express', 'MongoDB & SQLite', 'REST API Architecture', 'Authentication & Endpoints'],
        stats={'tasksDone': 0, 'filesCreated': 0, 'reviewsDone': 0},
        desk={'room': 'Orbital Station Beta', 'col': 2, 'row': 1}
    ).save()

    sarah = AgentDocument(
        agent_id='sarah',
        name='Sarah',
        role='QA & UI/UX Specialist',
        department='Design & QA',
        avatar='🎨',
        color='from-purple-500 to-pink-600',
        status='idle',
        status_text='Quality control matrix primed.',
        model='gemini-2.0-flash',
        system_prompt='You are Sarah, QA & Design Specialist. You verify UI styling, responsiveness, cross-browser compatibility, and API integrity.',
        skills=['UI/UX Testing', 'Responsiveness QA', 'API Validation', 'Accessibility'],
        stats={'tasksDone': 0, 'filesCreated': 0, 'reviewsDone': 0},
        desk={'room': 'Orbital Station Gamma', 'col': 3, 'row': 1}
    ).save()

    project = ProjectStateDocument(
        singleton_id='current_project',
        project_name='Mission Control Office',
        project_goal='Standing by for user voice/chat directive to build in parallel...',
        status='idle',
        progress=0
    ).save()

    print("[OK] MongoDB successfully reset with Michael, Dave, and Sarah!")

if __name__ == '__main__':
    reset()
