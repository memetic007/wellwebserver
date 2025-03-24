from flask import Flask, request, session, jsonify, g
import paramiko, time, uuid, os, signal
import base64
import re
import extract2json
import makeobjects2json
import sys
import utils
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = '397397397'  # for session cookies

# Check command line arguments for -welltest flag
HARDCODED_HOST = "user.dev.well.com" if "-welltest" in sys.argv else "well.com"

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
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors='replace')
        err = stderr.read().decode(errors='replace')
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
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode(errors='replace')
            err = stderr.read().decode(errors='replace')
        except Exception as e2:
            return False, f'Connection lost and reconnect failed: {str(e2)}'

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
    
    # Get command and conflist flag
    data = request.get_json()
    
    include_conflist = data.get('conflist', False)  # Default to False if not provided
    
    if not include_conflist:
        #conflist is false
        cmd = data.get('command')
        if not cmd:
            return jsonify({'error': 'No command provided'}), 400
            
        # Check if command starts with 'extract' (case insensitive)
        first_token = cmd.split()[0] if cmd.split() else ""
        if not first_token.lower() == "extract":
            return jsonify({'error': 'Command must start with "extract"'}), 400
    else:
        #conflist is true
        for attempt in range(2):
            success, result = execute_ssh_command(sess_id, 'cat .cfdir/.wscflist')
            if success:
                exit_status, conflist_out, conflist_err = result
                if exit_status == 0:
                    conflist = [line.strip() for line in conflist_out.splitlines() if line.strip() and '#' not in line]
                    break
            if attempt == 0:
                print("First conflist attempt failed, retrying...")
        else:  # No successful attempt
            return jsonify({'error': 'Failed to retrieve conference list'}), 500

        # Change from spaces to commas with no spaces
        cmd = 'extract -np ' + ','.join(conflist)

    print("command provided to extractconfcontent: " + cmd)

           
    # Execute the extract command
    success, result = execute_ssh_command(sess_id, cmd)
    
    if not success:
        return jsonify({'error': result}), 401
        
    exit_status, out, err = result
    # process the output of the extract command to line by line JSON
    out = extract2json.processrawextract(out)
    
    # convert the line by line JSON to a single JSON object
    
    if include_conflist:
        out = makeobjects2json.makeObjects(out,conflist)
    else:
        conflist = []
        out = makeobjects2json.makeObjects(out,conflist)

    # Build response
    response = {
        'exit_status': exit_status,
        'output': out,
        'data': json.loads(out)  # Parse the JSON string back to an object and include it in the response
    }
    
    # Only include conflist in response if it was requested and retrieved
    if include_conflist and conflist is not None:
        response['conflist'] = conflist
        
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

    success, result = execute_ssh_command(sess_id, 'cat .cfdir/.wscflist')                                     
    
    if not success:
        return jsonify({'error': result}), 401
        
    exit_status, output, error = result
    
    if exit_status != 0 or error:
        # if file doesn't exist, return empty list
        if "No such file" in error:
            cflist = []
            return jsonify({'cflist': cflist}), 200
        else:
            return jsonify({
                'error': 'Failed to read cflist',
                'details': error or 'Unknown error'
            }), 500

    # Format the output specific to cflist
    cflist = [line.strip() for line in output.splitlines() if line.strip()]
    return jsonify({'cflist': cflist}), 200

def execute_new_topic(ssh_client, decode_lines,conf,title):
        
    try:
       
        
        # Start interactive session
        channel = ssh_client.invoke_shell()
        
        # Function to wait for prompt with timeout
        def wait_for_prompt(timeout=5):
            start_time = time.time()
            buff = ''
            while 'ok (' not in buff.lower():
                if time.time() - start_time > timeout:
                    raise TimeoutError("Timed out waiting for prompt")
                if channel.recv_ready():
                    resp = channel.recv(9999)
                    buff += resp.decode('utf-8', errors='replace')
                time.sleep(0.1)
            return buff
            
        # Wait for initial "Ok (" prompt
        wait_for_prompt()
            
        # Send g conference command
        channel.send(f"!post -e \"{title}\" {conf}\n")
        time.sleep(0.1)
        for line in decode_lines:
            channel.send(line + "\n")
            
        channel.send(".\n")

        time.sleep(0.25)
        
        channel.close()
        
        return True, f"Successfully created new topic: {title}"
    except Exception as e:
        # Update last active time
        
        return False, f"Error creating new topic: {str(e)}"
       
        


def execute_post_reply(ssh_client, decoded_lines, conf, topic, debug_mode=False, option='post', title=''):
    try:
        # Choose command based on option
        
        command = f"post -n {conf} {topic}\n"
        
        stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True)

        # Write multiple lines to stdin
        for line in decoded_lines:
            stdin.write(line + "\n")
        stdin.write(".\n")
        # Ensure all data is sent
        stdin.flush()

        # Close the stdin channel
        stdin.close()   

        # Read output and handle bad characters with replacement
        output = stdout.read().decode("utf-8", errors='replace')
        error_output = stderr.read().decode("utf-8", errors='replace')

        # Check for common error patterns
        error_patterns = [
            "error", "invalid", "failed", "denied", "not found",
            "cannot", "unauthorized", "permission denied"
        ]
        
        # Check stderr first
        if error_output:
            return False, f"Command error: {error_output}"
            
        # Check stdout for error patterns
        output_lower = output.lower()
        for pattern in error_patterns:
            if pattern in output_lower:
                return False, f"Operation failed: {output}"

        # Check exit status
        if stdout.channel.recv_exit_status() != 0:
            return False, f"Command failed with non-zero exit status: {output}"

        return True, output

    except Exception as e:
        return False, f"Error executing post command: {str(e)}"

@app.route('/postreply', methods=['POST'])
def postreply():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not sess_id or sess_id not in sessions:
        return jsonify({'error': 'No active session. Please connect first.'}), 401
        
    # Get request data
    data = request.get_json()
    if not all(k in data for k in ['base64_content', 'conference', 'topic']):
        return jsonify({'error': 'Missing required parameters'}), 400
        
    # Get optional parameters with defaults
    option = data.get('option', 'post')
    title = data.get('title', '').strip()
    
    # Validate option
    if option not in ['post', 'newtopic']:
        return jsonify({'error': 'Invalid option. Must be "post" or "newtopic"'}), 400
        
    # Validate title for newtopic
    if option == 'newtopic' and not title:
        return jsonify({'error': 'Title is required for newtopic option'}), 400
     
    # Decode base64 content
    decoded_content = base64.b64decode(data['base64_content']).decode("utf-8")
    lines = decoded_content.strip().split('\n')  
    
    if option == 'post':
        

        try:
           
            
            
            # Get SSH client and try post reply
            ssh_client = sessions[sess_id]['ssh']
            success, result = execute_post_reply(
                ssh_client, 
                lines,
                data['conference'],
                data['topic'],
                debug_mode=app.debug,
                option=option,
                title=title
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
                        debug_mode=app.debug,
                        option=option,
                        title=title
                    )
                    
                except Exception as e:
                    return jsonify({'error': f'Reconnection failed: {str(e)}'}), 500
            
            if not success:
                return jsonify({'error': result}), 500
                
            # Check if hide parameter is exactly True and if so find post and hide it
            doHide = data.get('hide')
            if doHide is True:
                #find the post and hide it
                command = f"extract -s -1 -u {data['username']} {data['conference']} {data['topic']}"
                success, extract_result = execute_ssh_command(sess_id, command)
                if success:

                    out = extract_result[1]
                    outlines = out.splitlines()
                    
                    # Process lines from bottom to top (reverse order)
                    for line in reversed(outlines):
                        # Check if the line is not empty and first character is not whitespace
                        if line and not line[0].isspace():
                            # Split the line into tokens
                            tokens = line.split()
                            if tokens:
                                # Set handle to the first token
                                handle = tokens[0]
                                # Remove colon if present
                                if handle.endswith(':'):
                                    handle = handle[:-1]
                                
                                conf,topic,post = utils.conf_topic_post(handle)
                                command = f"post -h {conf} {topic} {post}"
                                success, postresult = execute_ssh_command(sess_id, command)
                                if success:
                                    print(f"Successfully hid post: {post}")
                                else:
                                    print(f"Failed to hide post: {post}")
                                
                                # Break out of the loop after processing a post
                                break

                            
                            
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

    elif option == 'newtopic':
        ssh_client = sessions[sess_id]['ssh']
        conference = data['conference']
        success, result = execute_new_topic(ssh_client, lines,conference,title)
        if not success:
            return jsonify({'error': result}), 500
        else:
            return jsonify({'success': True, 'output': result}), 200
        

def execute_sftp_put_file(ssh_client, relative_path, content_lines):
    """
    Transfers file content to a remote path using SFTP.
    
    Args:
        ssh_client: The SSH client to use for connection
        relative_path: The path relative to home directory where the file should be created/updated
        content_lines: List of strings to be written to the file
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Combine the list into a single string with newlines
        file_contents = '\n'.join(content_lines)
        if not file_contents.endswith('\n'):
            file_contents += '\n'
        
        try:
            sftp = ssh_client.open_sftp()
        except Exception as e:
            return False, f"Failed to open SFTP connection: {str(e)}"

        try:
            # Resolve the relative path to the absolute home directory path
            try:
                home_dir = sftp.normalize('.')
            except Exception as e:
                return False, f"Failed to resolve home directory: {str(e)}"

            # Make sure path is treated as relative to home
            if relative_path.startswith('/'):
                relative_path = relative_path[1:]
            
            remote_filepath = f"{home_dir}/{relative_path}"
            
            # Make sure directory exists
            try:
                dir_path = os.path.dirname(remote_filepath)
                if dir_path and dir_path != home_dir:
                    try:
                        sftp.stat(dir_path)
                    except FileNotFoundError:
                        return False, f"Directory {dir_path} not found"
                    except Exception as e:
                        return False, f"Error checking directory {dir_path}: {str(e)}"
            except Exception as e:
                return False, f"Error processing directory path: {str(e)}"
              
            # Write content directly to remote file
            try:
                with sftp.file(remote_filepath, 'w') as remote_file:
                    remote_file.write(file_contents)
            except PermissionError:
                return False, f"Permission denied writing to {remote_filepath}"
            except IOError as e:
                return False, f"IO Error writing to file: {str(e)}"
            except Exception as e:
                return False, f"Error writing to file: {str(e)}"

        finally:
            # Always try to close SFTP
            try:
                sftp.close()
            except:
                pass  # Ignore errors during close

        return True, f"Successfully transferred file to {relative_path}"

    except Exception as e:
        return False, f"Error executing SFTP file transfer: {str(e)}"

def execute_put_cflist(ssh_client, cflist_lines):
    """Legacy function that uses the new generalized function"""
    return execute_sftp_put_file(ssh_client, '.cfdir/.wscflist', cflist_lines)

@app.route('/put_cflist', methods=['POST'])
def put_cflist():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not sess_id or sess_id not in sessions:
        return jsonify({'error': 'No active session. Please connect first.'}), 401
        
    # Get request data
    data = request.get_json()
    if not data or 'cflist' not in data:
        return jsonify({'error': 'Missing cflist parameter'}), 400
        
    cflist = data['cflist']
    if not isinstance(cflist, list):
        return jsonify({'error': 'cflist must be a list of strings'}), 400
        
    try:
        # Get SSH client and try to update cflist using the generalized function
        ssh_client = sessions[sess_id]['ssh']
        success, result = execute_sftp_put_file(ssh_client, '.cfdir/.wscflist', cflist)
        
        # If failed, try to reconnect and retry once
        if not success:
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
                
                # Try update again
                success, result = execute_sftp_put_file(ssh_client, '.cfdir/.wscflist', cflist)
                
            except Exception as e:
                return jsonify({'error': f'Reconnection failed: {str(e)}'}), 500
        
        if not success:
            return jsonify({'error': result}), 500
            
        # Update last active time
        sessions[sess_id]['last_active'] = time.time()
        
        return jsonify({
            'success': True,
            'message': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to process put_cflist: {str(e)}'
        }), 500

@app.route('/forget_remember', methods=['POST'])
def forget_remember():
    # Get session ID
    sess_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not sess_id or sess_id not in sessions:
        return jsonify({'error': 'No active session. Please connect first.'}), 401
        
    # Get request data
    data = request.get_json()
    if not all(k in data for k in ['conference', 'topic']):
        return jsonify({'error': 'Missing required parameters. Need conference and topic.'}), 400
        
    conference = data['conference']
    topic = data['topic']
    option = data.get('option', 'forget')  # Default to 'forget' if not specified
    
    if option not in ['forget', 'remember']:
        return jsonify({'error': 'Option must be either "forget" or "remember"'}), 400
    
    try:
        # Get SSH client
        ssh_client = sessions[sess_id]['ssh']
        
        # Start interactive session
        channel = ssh_client.invoke_shell()
        
        # Function to wait for prompt with timeout
        def wait_for_prompt(timeout=5):
            start_time = time.time()
            buff = ''
            while 'ok (' not in buff.lower():
                if time.time() - start_time > timeout:
                    raise TimeoutError("Timed out waiting for prompt")
                if channel.recv_ready():
                    resp = channel.recv(9999)
                    buff += resp.decode('utf-8', errors='replace')
                time.sleep(0.1)
            return buff
            
        # Wait for initial "Ok (" prompt
        wait_for_prompt()
            
        # Send g conference command
        channel.send(f"g {conference}\n")
        
        # Wait for next "Ok (" prompt
        wait_for_prompt()
            
        # Send forget/remember command based on option
        channel.send(f"{option} {topic}\n")
        
        # Flush the channel
        channel.send('\n')
        
        # Wait 250ms
        time.sleep(0.25)
        
        # Close the channel
        channel.close()
        
        # Update last active time
        sessions[sess_id]['last_active'] = time.time()
        
        return jsonify({
            'success': True,
            'conference': conference,
            'topic': topic,
            'option': option,
            'message': f"Successfully executed {option} for {conference}.{topic}"
        }), 200
        
    except TimeoutError as e:
        return jsonify({
            'error': f'Timeout waiting for system response: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'Failed to process {option} request: {str(e)}'
        }), 500

# Add this after all your route definitions (just before if __name__ == '__main__':)
print("\n*** Registered Routes ***")
print("\n".join(f"- {rule}" for rule in app.url_map.iter_rules()))
print("\n")

if __name__ == '__main__':
    print("Starting Flask server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)

