from app_dir import create_app, db, UPLOAD_FOLDER
from flask import send_file, current_app

app = create_app()

@app.route("/uploads/<filename>")
def send_photo(filename):
    return send_file(f"{UPLOAD_FOLDER}/{filename}")

if __name__=="__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="localhost", port=8080)
