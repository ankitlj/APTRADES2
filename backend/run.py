from app import create_app
from app.config import load_config
from app.realtime import socketio

app = create_app()


if __name__ == "__main__":
    config = load_config()
    # socketio.run serves both the REST app and the websocket transport in dev.
    socketio.run(
        app,
        host=config.host,
        port=config.port,
        debug=config.debug,
        allow_unsafe_werkzeug=True,
    )
