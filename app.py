from flask import Flask, render_template
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start')
def start_canvas():
    subprocess.Popen("python air_canvas_backend.py", shell=True)
    return "Air Canvas Started!"

if __name__ == "__main__":
    app.run(debug=True)