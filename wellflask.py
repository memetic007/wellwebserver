from flask import Flask, request, session, jsonify, g
import paramiko, time, uuid, os, signal
import base64
import re
import extract2json
import makeobjects2json

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

def execute_ssh_command(sess_id, command):
    """
    Helper function to execute SSH commands with session validation and error handling
    
    Args:
        sess_id: The session ID to use
        command: The command to execute
        
    Returns:
        tuple: (success, result)
            - If success is True, result contains (exit_status, stdout, stderr)
            - If success is False, result contains error message
    """
    # Validate session
    if not sess_id or sess_id not in sessions:
        return False, 'No active session. Please connect first.'

    # Check idle timeout
    if time.time() - sessions[sess_id]['last_active'] > 1800:
        try:
            sessions[sess_id]['ssh'].close()
        except Exception:
            pass
        sessions.pop(sess_id, None)
        return False, 'Session timed out due to inactivity.'

    ssh_client = sessions[sess_id]['ssh']
    try:
        stdin, stdout, stderr = ssh_client.exec_command(command)
    except Exception as e:
        # Attempt reconnect on failure
        creds = sessions[sess_id]['creds']
        try:
            ssh_client.close()
        except:
            pass
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh_client.connect(**creds)
            sessions[sess_id]['ssh'] = ssh_client
            stdin, stdout, stderr = ssh_client.exec_command(command)
        except Exception as e2:
            return False, f'Connection lost and reconnect failed: {str(e2)}'

    # Read command output
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    
    # Update last active time
    sessions[sess_id]['last_active'] = time.time()
    
    return True, (exit_status, out, err)

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
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    
    # Get command
    cmd = request.get_json().get('command')
    if not cmd:
        return jsonify({'error': 'No command provided'}), 400

    # Execute command using helper function
    success, result = execute_ssh_command(sess_id, cmd)
    
    if not success:
        return jsonify({'error': result}), 401
        
    exit_status, out, err = result
    response = {'exit_status': exit_status, 'output': out}
    if err:
        response['error_output'] = err
    return jsonify(response), 200


@app.route('/extractconfcontent', methods=['POST'])
def extractconfcontent():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    
    # Get command
    cmd = request.get_json().get('command')
    if not cmd:
        return jsonify({'error': 'No command provided'}), 400
        
    # Check if command starts with 'extract' (case insensitive)
    first_token = cmd.split()[0] if cmd.split() else ""
    if not first_token.lower() == "extract":
        return jsonify({'error': 'Command must start with "extract"'}), 400
        
    print("command provided to extractconfcontent: " + cmd)

    # First get the conflist - try up to two times
    for attempt in range(2):
        success, result = execute_ssh_command(sess_id, 'cat .cfdir/.cflist')
        if success:
            exit_status, conflist_out, conflist_err = result
            if exit_status == 0:
                conflist = [line.strip() for line in conflist_out.splitlines() if line.strip()]
                break
        if attempt == 0:
            print("First conflist attempt failed, retrying...")
    else:  # No successful attempt
        return jsonify({'error': 'Failed to retrieve conference list'}), 500

    # Now execute the extract command
    success, result = execute_ssh_command(sess_id, cmd)
    
    if not success:
        return jsonify({'error': result}), 401
        
    exit_status, out, err = result
    # process the output of the extract command to line by line JSON
    out = extract2json.processrawextract(out)
    
    # convert the line by line JSON to a single JSON object
    out = makeobjects2json.makeObjects(out)

    # Return both conflist and extract output
    response = {
        'exit_status': exit_status,
        'output': out,
        'conflist': conflist
    }
    if err:
        response['error_output'] = err
    return jsonify(response), 200

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

# Update the shutdown route
@app.route('/shutdown', methods=['POST'])
def shutdown():
    try:
        # Get our own process ID
        pid = os.getpid()
        print("\nServer terminating...")  # Add termination message
        # Send ourselves a SIGTERM signal
        os.kill(pid, signal.SIGTERM)
        return jsonify({'message': 'Server shutting down...'}), 200
    except Exception as e:
        return jsonify({'error': f'Shutdown failed: {str(e)}'}), 500

@app.route('/cflist', methods=['GET'])
def get_cflist():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    
    # Execute command using helper function
    success, result = execute_ssh_command(sess_id, 'cat .cfdir/.cflist')
    
    if not success:
        return jsonify({'error': result}), 401
        
    exit_status, output, error = result
    
    if exit_status != 0 or error:
        return jsonify({
            'error': 'Failed to read cflist',
            'details': error or 'Unknown error'
        }), 500

    # Format the output specific to cflist
    cflist = [line.strip() for line in output.splitlines() if line.strip()]
    return jsonify({'cflist': cflist}), 200

def execute_post_reply(ssh_client, decoded_lines, conf, topic, debug_mode=False):
    """
    Execute post reply using interactive shell
    
    Args:
        ssh_client: Paramiko SSH client
        decoded_lines: List of lines to post
        conf: Conference name
        topic: Topic number
        debug_mode: Enable debug output
        
    Returns:
        tuple: (success, result)
            - If success is True, result contains output buffer
            - If success is False, result contains error message
    """
    try:
        # Open channel for interactive shell
        channel = ssh_client.invoke_shell()
        
        # Buffer for received data
        output_buffer = ""
        
        # Flag to track if we've seen the "ok (" pattern
        ok_pattern_seen = False
        
        # Wait for initial response
        while True:
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                output_buffer += data
                
                if debug_mode:
                    print(data, end="", flush=True)
                
                # Check for "ok (" pattern (case insensitive)
                if not ok_pattern_seen and re.search(r"ok \(", data, re.IGNORECASE):
                    ok_pattern_seen = True
                    
                    # Wait 300ms
                    time.sleep(0.3)
                    
                    # Send "post conf topic" with newline
                    channel.send(f"!post -n {conf} {topic}\n")
                    
                    # Wait 300ms
                    time.sleep(0.3)
                    
                    # Send each line with newline, wait 50ms after each
                    for line in decoded_lines:
                        channel.send(f"{line}\n")
                        time.sleep(0.05)
                    
                    # Send single dot with newline
                    channel.send(".\n")
                    
                    # Wait 100ms to collect final output
                    time.sleep(0.1)
                    break
            
            # Prevent CPU hogging
            time.sleep(0.1)
        
        # Collect any remaining output
        time.sleep(0.1)
        while channel.recv_ready():
            data = channel.recv(4096).decode("utf-8", errors="replace")
            output_buffer += data
            
            if debug_mode:
                print(data, end="", flush=True)
                
        channel.close()
        return True, output_buffer
        
    except Exception as e:
        return False, f"Error in post reply: {str(e)}"

@app.route('/postreply', methods=['POST'])
def post_reply():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not sess_id or sess_id not in sessions:
        return jsonify({'error': 'No active session. Please connect first.'}), 401
        
    # Get request data
    data = request.get_json()
    if not all(k in data for k in ['base64_content', 'conference', 'topic']):
        return jsonify({'error': 'Missing required parameters'}), 400
        
    try:
        # Decode base64 content
        decoded_content = base64.b64decode(data['base64_content']).decode("utf-8")
        lines = decoded_content.strip().split('\n')
        
        # Get SSH client and try post reply
        ssh_client = sessions[sess_id]['ssh']
        success, result = execute_post_reply(
            ssh_client, 
            lines,
            data['conference'],
            data['topic'],
            debug_mode=app.debug
        )
        
        # If failed, try to reconnect and retry once
        if not success and "Error in post reply" in result:
            try:
                # Get stored credentials
                creds = sessions[sess_id]['creds']
                
                # Close old connection
                try:
                    ssh_client.close()
                except:
                    pass
                
                # Create new connection
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(**creds)
                
                # Store new connection
                sessions[sess_id]['ssh'] = ssh_client
                
                # Try post reply again
                success, result = execute_post_reply(
                    ssh_client,
                    lines,
                    data['conference'],
                    data['topic'],
                    debug_mode=app.debug
                )
                
            except Exception as e:
                return jsonify({'error': f'Reconnection failed: {str(e)}'}), 500
        
        if not success:
            return jsonify({'error': result}), 500
            
        # Update last active time
        sessions[sess_id]['last_active'] = time.time()
        
        return jsonify({
            'success': True,
            'output': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to process post reply: {str(e)}'
        }), 500

# Add this after all your route definitions (just before if __name__ == '__main__':)
print("\n*** Registered Routes ***")
print("\n".join(f"- {rule}" for rule in app.url_map.iter_rules()))
print("\n")

if __name__ == '__main__':
    print("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)

