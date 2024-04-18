from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Get the request data
    req = request.get_json(force=True)

    # Process the request here
    action = req.get('queryResult').get('action')

    # Define responses for Dialogflow
    if action == "action_name":
        response_text = "This is a response from the webhook for action_name."
    else:
        response_text = "This is a default response from the webhook."

    # Return the response in JSON format
    return jsonify({
        'fulfillmentText': response_text
    })

if __name__ == '__main__':
    app.run(debug=True, port=8080)
