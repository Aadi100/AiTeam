"""
Adion backend (Flask)
Powered by MongoEngine & local MongoDB (mongodb://localhost:27017/devsquad).
Plans goals into parallel agent runs, answers questions, tracks token usage, and serves the voice assistant.
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Import database initializer
from database import init_db

# Import route blueprints
from routes.health import health_bp
from routes.runs import runs_bp
from routes.jobs import jobs_bp, mark_lost_on_boot
from routes.memory import memory_bp
from routes.schedules import schedules_bp, start_scheduler
from routes.voice import voice_bp
from routes.assistant import assistant_bp
from routes.usage import usage_bp
from routes.pc import pc_bp
from routes.files import files_bp
from routes.chats import chats_bp
from auth import auth_bp, require_auth

load_dotenv()


def create_app():
    app = Flask(__name__)

    # Enable CORS for Next.js frontend (running on port 3000 or any origin)
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    # Initialize MongoEngine connection to local MongoDB
    init_db(app)

    # Register all API Blueprints with prefix /api
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(runs_bp, url_prefix='/api')
    app.register_blueprint(jobs_bp, url_prefix='/api')
    app.register_blueprint(memory_bp, url_prefix='/api')
    app.register_blueprint(schedules_bp, url_prefix='/api')
    app.register_blueprint(voice_bp, url_prefix='/api')
    app.register_blueprint(assistant_bp, url_prefix='/api')
    app.register_blueprint(usage_bp, url_prefix='/api')
    app.register_blueprint(pc_bp, url_prefix='/api')
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(chats_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.before_request(require_auth)
    mark_lost_on_boot()
    from orchestrator.engine import recover_interrupted
    recover_interrupted()
    start_scheduler()

    @app.route('/')
    def root():
        return jsonify({
            'name': 'Adion Engine',
            'version': '1.0.0',
            'status': 'online',
            'database': 'MongoDB via MongoEngine (mongodb://localhost:27017/devsquad)',
            'apiEndpoints': [
                '/api/health',
                '/api/tasks',
                '/api/tasks/parallel',
                '/api/agents',
                '/api/agents/pause',
                '/api/agents/resume',
                '/api/training/pairs',
                '/api/training/models',
                '/api/training/synthesize',
                '/api/training/train',
                '/api/training/export',
                '/api/messages',
                '/api/project',
                '/api/research'
            ]
        })

    return app

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n[INFO] Adion backend starting on http://localhost:{port}")
    print(f"[OK] Connected to local MongoDB via MongoEngine")
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=port, debug=False, threaded=True)
