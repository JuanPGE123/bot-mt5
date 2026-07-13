"""
Blueprint de autenticación. Login hardcodeado por requisito del proyecto.
"""
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from config import AUTH_USERNAME, AUTH_PASSWORD, DEMO_USERNAME, DEMO_PASSWORD

auth_bp = Blueprint("auth", __name__)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            session["is_demo"] = False
            return redirect(url_for("dashboard"))
        if username == DEMO_USERNAME and password == DEMO_PASSWORD:
            session["logged_in"] = True
            session["username"] = DEMO_USERNAME
            session["is_demo"] = True
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html", demo_username=DEMO_USERNAME)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
