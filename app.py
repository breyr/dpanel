from flask import Flask, render_template
import docker

app = Flask(__name__)
client = docker.from_env()


@app.route("/")
def index():
    # get containers
    containers = client.containers.list(all=True)
    return render_template("index.html", containers=containers)


@app.route("/info/<containerId>")
def info(containerId):
    # get container information
    return client.containers.get(container_id=containerId).attrs


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
