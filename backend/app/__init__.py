from pathlib import Path

from flask import Flask, abort, request, send_from_directory
import re
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from .config import Config
import logging
from sqlalchemy import text
import os

db = SQLAlchemy()


def _get_frontend_dist_dir():
    """Return the frontend build directory bundled into the Docker image."""
    env_dir = os.environ.get("FRONTEND_DIST_DIR")
    if env_dir:
        return Path(env_dir)
    # In the production image, backend code is copied to /app/app and the
    # frontend build output is copied to /app/static.
    return Path(__file__).resolve().parents[1] / "static"


def _register_frontend_routes(app):
    dist_dir = _get_frontend_dist_dir()
    index_file = dist_dir / "index.html"

    if not index_file.is_file():
        return

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        # Keep API 404s as API 404s instead of returning the SPA shell.
        if path == "admin_api" or path.startswith("admin_api/"):
            abort(404)
        if path == "health":
            abort(404)

        requested_file = dist_dir / path
        if path and requested_file.is_file():
            # Only content-hashed assets get immutable caching. HTML and legacy
            # filenames must revalidate so deployments remain visible on refresh.
            versioned = bool(re.search(r'\.[0-9a-f]{8,}(?:\.(?:async|chunk))?\.(?:js|css)$', path))
            compressed = requested_file.suffix in ('.js', '.css') and Path(str(requested_file) + '.gz').is_file()
            use_gzip = compressed and request.accept_encodings['gzip'] > 0
            response = send_from_directory(
                dist_dir, path + '.gz' if use_gzip else path,
                mimetype='text/javascript' if requested_file.suffix == '.js' else ('text/css' if requested_file.suffix == '.css' else None),
                max_age=31536000 if versioned else None,
            )
            if versioned:
                response.cache_control.immutable = True
            if compressed:
                response.vary.add('Accept-Encoding')
            if use_gzip and response.status_code != 304:
                response.headers['Content-Encoding'] = 'gzip'
            return response

        # A missing lazy-loaded asset is a 404, not HTML disguised as JavaScript.
        if path.endswith(('.js', '.css', '.gz', '.map')) or path.startswith('static/'):
            abort(404)
        response = send_from_directory(dist_dir, "index.html")
        response.cache_control.no_cache = True
        return response


def create_app(config_override=None):
    # Disable Flask's built-in /static route so the bundled Umi assets under
    # FRONTEND_DIST_DIR/static are served by serve_frontend below.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    from .security import scope
    from .security.reporting import redact_global_metrics
    app.after_request(redact_global_metrics)
    from werkzeug.exceptions import HTTPException
    from flask import jsonify
    @app.errorhandler(HTTPException)
    def api_error(error):
        return jsonify(Code=error.code, Message=error.description, Data=None), error.code

    # 初始化扩展
    db.init_app(app)
    CORS(app)

    # 注册蓝图
    from .routes import main as main_blueprint
    from .routes import api_v1 as api_v1_blueprint

    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_v1_blueprint)

    # 只在主进程中测试数据库连接
    if not app.config.get('TESTING') and not os.environ.get('WERKZEUG_RUN_MAIN'):
        with app.app_context():
            try:
                db.session.execute(text('SELECT 1'))
                print("数据库连接测试成功！")
            except Exception as e:
                print(f"数据库连接测试失败: {str(e)}")
                logging.error(f"数据库连接错误: {str(e)}")

    _register_frontend_routes(app)

    return app
