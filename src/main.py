#!/usr/bin/env python
import os

@app.route('/')
def hello():
    return 'Hello, World!'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print "Starting app on port %d" % port
    app.run(host='0.0.0.0', port=port, debug=True)
