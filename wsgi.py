''' gunicorn server for grimoire '''
from grimoire import app

if __name__ == "__main__":
    app.run()
