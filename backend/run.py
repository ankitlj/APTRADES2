from app import create_app
from app.config import load_config

app = create_app()


if __name__ == "__main__":
    config = load_config()
    app.run(host=config.host, port=config.port, debug=config.debug)
