from flask import Flask, redirect, render_template, url_for

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/<name>")
def undefined_page(name):
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
    #app.run()
    