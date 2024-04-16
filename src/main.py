from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def good_conditions():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
