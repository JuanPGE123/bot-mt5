"""
Blueprint: Panel de Noticias en Tiempo Real (scraping interno, sin APIs externas).
"""
from flask import Blueprint, request, jsonify

from routes.auth import login_required
from services.news_scraper import get_news_for_pair

news_bp = Blueprint("news", __name__, url_prefix="/news")


@news_bp.route("/fetch")
@login_required
def fetch():
    pair = request.args.get("pair", "EURUSD")
    resultado = get_news_for_pair(pair)
    return jsonify(resultado)
