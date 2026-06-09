
"""WSGI entrypoint for running MyPick with Gunicorn in production."""

from app import app

application = app
