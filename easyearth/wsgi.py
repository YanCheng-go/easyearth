from easyearth.app import app

# This will be used by gunicorn to run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3781)