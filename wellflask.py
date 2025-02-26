from flask import Flask, request, session, jsonify, g
import paramiko, time, uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = '397397397'  # for session cookies

# Hardcoded host value
HARDCODED_HOST = "well.com"

# In-memory cache for active SSH sessions
sessions = {}  # { session_id: { 'ssh': SSHClient, 'creds': {host, user, pwd}, 'last_active': time.time() } }

# Helper: cleanup idle sessions (could be called periodically or each request)
def cleanup_idle_sessions():
    now = time.time()
    to_close = [sid for sid, data in sessions.items() if now - data['last_active'] > 1800]
    for sid in to_close:
        try:
            sessions[sid]['ssh'].close()
        except Exception:
            pass
        sessions.pop(sid, None)

@app.route('/connect', methods=['POST'])
def connect():
    data = request.get_json()
    user = data.get('username')
    pwd  = data.get('password')
    if not user or not pwd:
        return jsonify({'error': 'Missing credentials'}), 400

    # Use hardcoded host instead of getting from request
    host = HARDCODED_HOST

    # Establish SSH connection
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=pwd, timeout=5)
    except Exception as e:
        return jsonify({'error': f'SSH connection failed: {str(e)}'}), 401

    # Create a session entry
    sess_id = str(uuid.uuid4())
    sessions[sess_id] = {
        'ssh': client,
        'creds': {'hostname': host, 'username': user, 'password': pwd},
        'last_active': time.time()
    }
    # Use Flask session or token to track user session (here we return session ID as token for simplicity)
    session['session_id'] = sess_id  # stored in cookie (signed)
    return jsonify({'message': 'Connected', 'session_id': sess_id}), 200

@app.route('/execute', methods=['POST'])
def execute():
    # Identify session (either from cookie or from request token)
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not sess_id or sess_id not in sessions:
        return jsonify({'error': 'No active session. Please connect first.'}), 401

    # Enforce rate limiting (very basic example, should use a better mechanism in production)
    # (This is just a placeholder comment; use Flask-Limiter or similar for actual rate limiting.)

    # Check idle timeout
    if time.time() - sessions[sess_id]['last_active'] > 1800:
        # Session expired
        try:
            sessions[sess_id]['ssh'].close()
        except Exception:
            pass
        sessions.pop(sess_id, None)
        return jsonify({'error': 'Session timed out due to inactivity.'}), 440

    cmd = request.get_json().get('command')
    if not cmd:
        return jsonify({'error': 'No command provided'}), 400

    ssh_client = sessions[sess_id]['ssh']
    try:
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
    except Exception as e:
        # Attempt reconnect on failure
        creds = sessions[sess_id]['creds']
        try:
            ssh_client.close()
        except: pass
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh_client.connect(**creds)
        except Exception as e2:
            return jsonify({'error': 'Connection lost and reconnect failed: '+str(e2)}), 500
        sessions[sess_id]['ssh'] = ssh_client
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
    # Read command output
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    sessions[sess_id]['last_active'] = time.time()
    result = {'exit_status': exit_status, 'output': out}
    if err:
        result['error_output'] = err
    return jsonify(result), 200

# Optionally, an endpoint to disconnect (logout)
@app.route('/disconnect', methods=['POST'])
def disconnect():
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if sess_id and sess_id in sessions:
        try:
            sessions[sess_id]['ssh'].close()
        except: pass
        sessions.pop(sess_id, None)
    session.clear()
    return jsonify({'message': 'Disconnected'}), 200

# (In production, you might run a background job to call cleanup_idle_sessions periodically)

# Add this new route to wellflask.py
@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return jsonify({'message': 'Server shutting down...'})

# Add this at the end of the file
if __name__ == '__main__':
    print("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
