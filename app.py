from flask import Flask, render_template
import docker

app = Flask(__name__)
client = docker.from_env()


@app.route("/")
def index():
    containers = client.containers.list()
    return render_template("index.html", containers=containers)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
