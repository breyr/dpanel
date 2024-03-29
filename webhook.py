from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
  event = request.headers.get('X-GitHub-Event')
  # Verify that the request is from GitHub
  if event == 'push':
    # Stopping and removing existing containers, networks, and volumes
    subprocess.run(["docker-compose", "down", "--volumes", "--remove-orphans"])

    # Remove existing images (optional, uncomment if needed)
    # subprocess.run(["docker", "rmi", "$(`docker images -q`)", "-f"])

    # Pull the latest changes from GitHub
    subprocess.run(["git", "pull", "origin", "--force"])

    # Run docker-compose
    subprocess.run(["docker-compose", "up", "--build", "-d"])

    return 'Update and deployment completed successfully', 200
  elif event == 'ping':
    return 'Ping event received successfully', 200
  else:
    return 'Unsupported event', 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1470)
