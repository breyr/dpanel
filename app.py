from flask import Flask, render_template, jsonify
import docker
app = Flask(__name__)
client = docker.from_env()


@app.route("/")
def index():
    # get containers
    containers = client.containers.list(all=True)
    return render_template("containers.html",  current_page='containers')


@app.route("/get_containers")
def get_containers():
    containers = client.containers.list(all=True)
    return jsonify([container.attrs for container in containers])


@app.route("/images")
def images():
    return render_template("images.html", current_page='images')


@app.route("/volumes")
def volumes():
    return render_template("volumes.html", current_page='volumes')


@app.route("/info/<containerId>")
def info(containerId):
    # get container information
    return client.containers.get(container_id=containerId).attrs


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
