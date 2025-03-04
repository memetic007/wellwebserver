import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import json
import base64

class WellClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Well SSH Client")
        self.root.geometry("800x900")  # Increased height further
        self.session_id = None
        
        # Create frames
        self.login_frame = tk.Frame(root)
        self.command_frame = tk.Frame(root)
        
        # Add shutdown button at the top of the window
        self.shutdown_button = tk.Button(root, text="Shutdown Server", 
                                       command=self.shutdown_server, 
                                       bg="red", fg="white")
        self.shutdown_button.pack(anchor="ne", padx=5, pady=5)
        
        # Login frame widgets
        tk.Label(self.login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.username_entry = tk.Entry(self.login_frame, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        self.username_entry.insert(0, "memetic")  # Set default username
        
        tk.Label(self.login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.password_entry = tk.Entry(self.login_frame, width=30, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        self.password_entry.insert(0, "land+High007")  # Set default password
        
        self.login_button = tk.Button(self.login_frame, text="Connect", command=self.connect)
        self.login_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Command frame widgets
        command_buttons_frame = tk.Frame(self.command_frame)
        command_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        # Add Get Conflist button above command input
        self.get_conflist_button = tk.Button(command_buttons_frame, text="Get Conflist", command=self.get_full_conflist)
        self.get_conflist_button.pack(side=tk.LEFT, padx=5)
        
        tk.Label(command_buttons_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        
        # Add extract checkbox
        self.extract_var = tk.BooleanVar()
        self.extract_checkbox = tk.Checkbutton(command_buttons_frame, 
                                             text="Extract", 
                                             variable=self.extract_var)
        self.extract_checkbox.pack(side=tk.LEFT, padx=5)
        
        self.command_entry = tk.Entry(self.command_frame, width=80)
        self.command_entry.pack(fill="x", padx=5, pady=5)
        self.command_entry.bind("<Return>", lambda event: self.send_command())
        
        button_frame = tk.Frame(self.command_frame)
        button_frame.pack(fill="x", padx=5)
        
        self.send_button = tk.Button(button_frame, text="Send", command=self.send_command)
        self.send_button.pack(side=tk.LEFT, padx=5)
        
        self.confs_button = tk.Button(button_frame, text="Confs", command=self.get_confs)
        self.confs_button.pack(side=tk.LEFT, padx=5)
        
        # Create frame for Output label and Clear button
        output_frame = tk.Frame(self.command_frame)
        output_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(output_frame, text="Output:").pack(side=tk.LEFT)
        self.clear_button = tk.Button(output_frame, text="Clear", command=self.clear_output)
        self.clear_button.pack(side=tk.RIGHT)
        
        self.output_text = scrolledtext.ScrolledText(self.command_frame, width=80, height=25)
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Reply frame
        tk.Label(self.command_frame, text="Reply:").pack(anchor="w", padx=5, pady=5)
        self.reply_text = scrolledtext.ScrolledText(self.command_frame, width=80, height=10)
        self.reply_text.pack(fill="x", padx=5, pady=5)
        
        # Frame for buttons at bottom
        bottom_frame = tk.Frame(self.command_frame)
        bottom_frame.pack(fill="x", padx=5, pady=(5, 15))  # Added more bottom padding
        
        # Submit Reply button
        self.submit_reply_button = tk.Button(bottom_frame, text="Submit Reply", command=self.submit_reply)
        self.submit_reply_button.pack(side=tk.LEFT, padx=5)
        
        # Reconnect button
        self.reconnect_button = tk.Button(bottom_frame, text="Reconnect", command=self.reconnect)
        self.reconnect_button.pack(side=tk.LEFT, padx=5)
        
        # Move disconnect button to bottom frame
        self.disconnect_button = tk.Button(bottom_frame, text="Disconnect", command=self.disconnect)
        self.disconnect_button.pack(side=tk.LEFT, padx=5)
        
        # Start with login frame
        self.login_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Server URL
        self.server_url = "http://localhost:5000"
    
    def connect(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password are required")
            return
        
        try:
            response = requests.post(
                f"{self.server_url}/connect",
                json={"username": username, "password": password},
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id")
                self.login_frame.pack_forget()
                self.command_frame.pack(fill="both", expand=True, padx=10, pady=10)
                self.output_text.insert(tk.END, "Connected to server. Ready to execute commands.\n")
                self.command_entry.focus()
            else:
                error_msg = response.json().get("error", "Unknown error")
                messagebox.showerror("Connection Failed", f"Error: {error_msg}")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
    
    def send_command(self):
        command = self.command_entry.get()
        if not command:
            return
        
        if not self.session_id:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        try:
            # Choose endpoint based on extract checkbox
            endpoint = '/extractconfcontent' if self.extract_var.get() else '/execute'
            
            response = requests.post(
                f"{self.server_url}{endpoint}",
                headers={"X-Session-ID": self.session_id},
                json={"command": command},
                timeout=1000
            )
            
            self.command_entry.delete(0, tk.END)
            
            if response.status_code == 200:
                data = response.json()
                self.output_text.insert(tk.END, f"\n> {command}\n")
                
                output = data.get("output", "")
                if output:
                    self.output_text.insert(tk.END, output)
                
                error_output = data.get("error_output", "")
                if error_output:
                    self.output_text.insert(tk.END, f"ERROR: {error_output}\n")
                
                self.output_text.see(tk.END)
            else:
                error_msg = response.json().get("error", "Unknown error")
                self.output_text.insert(tk.END, f"\nError executing command: {error_msg}\n")
                self.output_text.see(tk.END)
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError: {str(e)}\n")
            self.output_text.see(tk.END)
    
    def disconnect(self):
        if self.session_id:
            try:
                requests.post(
                    f"{self.server_url}/disconnect",
                    headers={"X-Session-ID": self.session_id}
                )
            except:
                pass
            
            self.session_id = None
        
        self.command_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.username_entry.focus()

    def shutdown_server(self):
        if messagebox.askyesno("Confirm Shutdown", "Are you sure you want to shut down the server?"):
            try:
                self.output_text.insert(tk.END, "\nInitiating server shutdown...\n")  # Add message to console
                self.output_text.see(tk.END)
                requests.post(f"{self.server_url}/shutdown")
                messagebox.showinfo("Success", "Server shutdown initiated")
                self.disconnect()  # Clean up client state
            except requests.exceptions.ConnectionError:
                # This is expected - server killed the connection
                self.output_text.insert(tk.END, "Server has terminated.\n")  # Add termination message
                self.output_text.see(tk.END)
                messagebox.showinfo("Success", "Server has been shut down")
                self.disconnect()
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error shutting down server: {str(e)}")

    def get_cflist(self):
        if not self.session_id:
            messagebox.showerror("Error", "Not connected to server")
            return None
        
        try:
            response = requests.get(
                f"{self.server_url}/cflist",
                headers={"X-Session-ID": self.session_id},
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('cflist', [])
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.output_text.insert(tk.END, f"\nError getting cflist: {error_msg}\n")
                self.output_text.see(tk.END)
                return None
                
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError: {str(e)}\n")
            self.output_text.see(tk.END)
            return None

    def submit_reply(self):
        if not self.session_id:
            messagebox.showerror("Error", "Not connected to server")
            return
            
        # Get reply text and encode as base64
        reply_text = self.reply_text.get("1.0", tk.END)
        if not reply_text.strip():
            messagebox.showerror("Error", "Reply text is empty")
            return
            
        try:
            # Encode the text as base64
            base64_content = base64.b64encode(reply_text.encode()).decode()
            
            # Send to server
            response = requests.post(
                f"{self.server_url}/postreply",
                headers={"X-Session-ID": self.session_id},
                json={
                    "base64_content": base64_content,
                    "conference": "test",
                    "topic": "2264"
                },
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                self.output_text.insert(tk.END, "\n--- Reply Submitted ---\n")
                self.output_text.insert(tk.END, data.get('output', ''))
                self.output_text.see(tk.END)
                
                # Clear reply box after successful submission
                self.reply_text.delete("1.0", tk.END)
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.output_text.insert(tk.END, f"\nError submitting reply: {error_msg}\n")
                self.output_text.see(tk.END)
                
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError: {str(e)}\n")
            self.output_text.see(tk.END)

    def get_confs(self):
        if not self.session_id:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        try:
            response = requests.get(
                f"{self.server_url}/cflist",
                headers={"X-Session-ID": self.session_id},
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                self.output_text.insert(tk.END, "\n--- Conferences ---\n")
                for conf in data.get('cflist', []):
                    self.output_text.insert(tk.END, f"{conf}\n")
                self.output_text.see(tk.END)
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.output_text.insert(tk.END, f"\nError getting conferences: {error_msg}\n")
                self.output_text.see(tk.END)
                
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError: {str(e)}\n")
            self.output_text.see(tk.END)

    def reconnect(self):
        """Reconnect using stored credentials"""
        if not hasattr(self, 'username_entry') or not hasattr(self, 'password_entry'):
            messagebox.showerror("Error", "No stored credentials")
            return
            
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Missing credentials")
            return
            
        try:
            response = requests.post(
                f"{self.server_url}/connect",
                json={
                    "username": username,
                    "password": password
                },
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get('session_id')
                self.output_text.insert(tk.END, "\n--- Reconnected ---\n")
                self.output_text.see(tk.END)
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.output_text.insert(tk.END, f"\nReconnection failed: {error_msg}\n")
                self.output_text.see(tk.END)
                
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError during reconnection: {str(e)}\n")
            self.output_text.see(tk.END)

    def clear_output(self):
        """Clear the output text box"""
        self.output_text.delete("1.0", tk.END)

    def get_full_conflist(self):
        """Get conflist using extractconfcontent route"""
        if not self.session_id:
            messagebox.showerror("Error", "Not connected to server")
            return
            
        try:
            response = requests.post(
                f"{self.server_url}/extractconfcontent",
                headers={"X-Session-ID": self.session_id},
                json={"conflist": True},
                timeout=1000
            )
            
            if response.status_code == 200:
                data = response.json()
                self.output_text.insert(tk.END, "\n--- Full Conference List ---\n")
                
                # Display the conflist from the response
                if 'conflist' in data:
                    for conf in data['conflist']:
                        self.output_text.insert(tk.END, f"{conf}\n")
                
                # Display any output from the extract command
                output = data.get('output', '')
                if output:
                    self.output_text.insert(tk.END, "\n--- Extract Output ---\n")
                    self.output_text.insert(tk.END, output)
                
                self.output_text.see(tk.END)
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.output_text.insert(tk.END, f"\nError getting conflist: {error_msg}\n")
                self.output_text.see(tk.END)
                
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError: {str(e)}\n")
            self.output_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = WellClient(root)
    root.mainloop() 