import os
from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    port = Config.PORT
    debug = Config.DEBUG
    print(f"🚀 Serveur Flask démarré sur http://127.0.0.1:{port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
