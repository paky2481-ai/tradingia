import os

def load_stylesheet() -> str:
    path = os.path.join(os.path.dirname(__file__), "dark_theme.qss")
    with open(path, "r") as f:
        return f.read()
