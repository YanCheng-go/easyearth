from easyearth import init_api

app = init_api()  # Create the app as a module-level variable

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3781)
