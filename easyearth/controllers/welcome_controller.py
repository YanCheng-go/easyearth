"""Welcome Controller for EasyEarth."""
from flask import Blueprint, send_from_directory
import os

def welcome():
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    return send_from_directory(static_dir, 'welcome.html')