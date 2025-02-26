import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import json

class WellClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Well SSH Client")
        self.root.geometry("800x600")
        self.session_id = None
        
        # Create frames
        self.login_frame = tk.Frame(root)
        self.command_frame = tk.Frame(root)
        
        # Login frame widgets
        tk.Label(self.login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.username_entry = tk.Entry(self.login_frame, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(self.login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.password_entry = tk.Entry(self.login_frame, width=30, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        
        self.login_button = tk.Button(self.login_frame, text="Connect", command=self.connect)
        self.login_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Command frame widgets
        tk.Label(self.command_frame, text="Command:").pack(anchor="w", padx=5, pady=5)
        self.command_entry = tk.Entry(self.command_frame, width=80)
        self.command_entry.pack(fill="x", padx=5, pady=5)
        self.command_entry.bind("<Return>", lambda event: self.send_command())
        
        self.send_button = tk.Button(self.command_frame, text="Send", command=self.send_command)
        self.send_button.pack(anchor="w", padx=5, pady=5)
        
        tk.Label(self.command_frame, text="Output:").pack(anchor="w", padx=5, pady=5)
        self.output_text = scrolledtext.ScrolledText(self.command_frame, width=80, height=25)
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.disconnect_button = tk.Button(self.command_frame, text="Disconnect", command=self.disconnect)
        self.disconnect_button.pack(anchor="w", padx=5, pady=10)
        
        # Add shutdown button next to disconnect button
        self.shutdown_button = tk.Button(self.command_frame, text="Shutdown Server", 
                                        command=self.shutdown_server, 
                                        bg="red", fg="white")
        self.shutdown_button.pack(anchor="w", padx=5, pady=10)
        
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
                timeout=10
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
            response = requests.post(
                f"{self.server_url}/execute",
                headers={"X-Session-ID": self.session_id},
                json={"command": command},
                timeout=30
            )
            
            self.command_entry.delete(0, tk.END)
            
            if response.status_code == 200:
                data = response.json()
                self.output_text.insert(tk.END, f"\n> {command}\n")
                
                # Display the actual command output, not the JSON
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
                response = requests.post(f"{self.server_url}/shutdown")
                if response.status_code == 200:
                    messagebox.showinfo("Success", "Server is shutting down")
                    self.disconnect()  # Disconnect client since server is going down
                else:
                    messagebox.showerror("Error", "Failed to shut down server")
            except Exception as e:
                messagebox.showerror("Error", f"Error shutting down server: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WellClient(root)
    root.mainloop() 