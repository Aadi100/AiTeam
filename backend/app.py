"""
DevSquad Standalone Python Flask Backend Server
Powered by MongoEngine & local MongoDB (mongodb://localhost:27017/devsquad).
Provides REST endpoints for autonomous worker nodes, concurrent multi-task batch execution,
continuous learning flywheel, dataset synthesis, and telemetry.
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Import database initializer
from database import init_db

# Import route blueprints
from routes.health import health_bp
from routes.tasks import tasks_bp
from routes.agents import agents_bp
from routes.training import training_bp
from routes.messages import messages_bp
from routes.project import project_bp
from routes.research import research_bp

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
    app.register_blueprint(tasks_bp, url_prefix='/api')
    app.register_blueprint(agents_bp, url_prefix='/api')
    app.register_blueprint(training_bp, url_prefix='/api')
    app.register_blueprint(messages_bp, url_prefix='/api')
    app.register_blueprint(project_bp, url_prefix='/api')
    app.register_blueprint(research_bp, url_prefix='/api')

    @app.route('/')
    def root():
        return jsonify({
            'name': 'DevSquad Python Flask Engine',
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
    print(f"\n[INFO] DevSquad Flask Backend starting on http://localhost:{port}")
    print(f"[OK] Connected to local MongoDB via MongoEngine")
    app.run(host='0.0.0.0', port=port, debug=False)
