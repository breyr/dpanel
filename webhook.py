from flask import Flask, request
import subprocess
import os
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

@app.route('/webhook', methods=['POST'])
def webhook():
  event = request.headers.get('X-GitHub-Event')
  # Verify that the request is from GitHub
  if event == 'push':
    try:
      # Stopping and removing existing containers, networks, and volumes
      subprocess.check_call(["docker-compose", "down", "--volumes", "--remove-orphans"])

      # Check if the 'upstream' remote exists
      remotes = subprocess.check_output(["git", "remote"]).decode('utf-8').split('\n')

      if 'upstream' not in remotes:
        # Add the original repository as a remote named 'upstream'
        subprocess.check_call(["git", "remote", "add", "upstream", "https://github.com/breyr/dpanel.git"])

      # Fetch the branches and their commits from the 'upstream'
      subprocess.check_call(["git", "fetch", "upstream"])

      # Merge the changes from the 'upstream/main' into your local 'master' branch
      subprocess.check_call(["git", "merge", "upstream/main"])

      # Run docker-compose
      subprocess.check_call(["docker-compose", "up", "--build", "-d"])
    except subprocess.CalledProcessError as e:
      logging.error(f"Subprocess failed with error {e}")
      return 'Update and deployment failed', 500
  elif event == 'ping':
    return 'Ping event received successfully', 200
  else:
    return 'Unsupported event', 400

if __name__ == '__main__':
  port = int(os.getenv('PORT', 1470))  # Use environment variable for port
  app.run(host='0.0.0.0', port=port)