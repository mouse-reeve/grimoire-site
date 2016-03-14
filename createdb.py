from grimoire import app, models

with app.app_context():
    models.db.create_all()
