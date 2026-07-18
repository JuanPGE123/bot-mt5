"""
Punto de entrada de la aplicación Flask.
Backtesting & Scalping Analytics — plataforma 100% local, sin APIs externas.
"""
import os

from flask import Flask, render_template, redirect, url_for

import config
from models import init_db, seed_demo_data
from routes.auth import auth_bp, login_required
from routes.data import data_bp
from routes.backtest import backtest_bp
from routes.news import news_bp
from routes.journal import journal_bp
from routes.entradas import entradas_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 35 * 1024 * 1024  # 35 MB (CSV + 3 imágenes: macro/intermedia/micro)

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    init_db()

    # Perfil DemoUser/Showcase (Punto 4): se puebla una única vez con datos
    # ficticios, aislado en su propia base de datos (nunca toca datos reales).
    seed_demo_data(config.DEMO_DB_PATH)

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(entradas_bp)

    @app.route("/")
    def root():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
