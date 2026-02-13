import flask from Flask , jsonify , request , render_template

app = flask.Flask(__name__)

@app.route('/')
def index():
    return flask.render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True , port=1536)