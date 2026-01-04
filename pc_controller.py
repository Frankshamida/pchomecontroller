from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import platform
import json
import subprocess
import psutil
import threading
import time
from datetime import datetime, timedelta

class PCControlHandler(BaseHTTPRequestHandler):
    timer_thread = None
    shutdown_time = None
    
    # Store the HTML content
    HTML_CONTENT = None
    
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            # Serve the HTML interface
            self._set_headers(200, 'text/html')
            if PCControlHandler.HTML_CONTENT:
                self.wfile.write(PCControlHandler.HTML_CONTENT.encode('utf-8'))
            else:
                self.wfile.write(b'<h1>HTML file not found. Place index.html in the same folder.</h1>')
        
        elif self.path == '/manifest.json':
            # PWA manifest for "Add to Home Screen"
            self._set_headers(200, 'application/json')
            manifest = {
                "name": "PC Remote Control",
                "short_name": "PC Control",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#667eea",
                "theme_color": "#667eea",
                "orientation": "portrait",
                "icons": [{
                    "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='0.9em' font-size='90'%3E🖥️%3C/text%3E%3C/svg%3E",
                    "sizes": "512x512",
                    "type": "image/svg+xml"
                }]
            }
            self.wfile.write(json.dumps(manifest).encode())
        
        elif self.path == '/test':
            self._set_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "Server is running",
                "pc_name": platform.node()
            }).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b'{"status": "error", "message": "Not found"}')
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            command = data.get('command', '')
            
            result = self.handle_command(command, data)
            self._set_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({
                "status": "error",
                "message": str(e)
            }).encode())
    
    def handle_command(self, command, data):
        system = platform.system()
        
        # Power Commands
        if command == 'shutdown':
            if system == 'Windows':
                os.system('shutdown /s /t 5')
            elif system == 'Linux':
                os.system('shutdown -h +1')
            return {"status": "ok", "message": "Shutting down in 5 seconds..."}
        
        elif command == 'restart':
            if system == 'Windows':
                os.system('shutdown /r /t 5')
            elif system == 'Linux':
                os.system('shutdown -r +1')
            return {"status": "ok", "message": "Restarting in 5 seconds..."}
        
        elif command == 'logout':
            if system == 'Windows':
                os.system('shutdown /l')
            elif system == 'Linux':
                os.system('pkill -KILL -u $USER')
            return {"status": "ok", "message": "Logging out..."}
        
        elif command == 'sleep':
            if system == 'Windows':
                os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
            elif system == 'Linux':
                os.system('systemctl suspend')
            return {"status": "ok", "message": "Entering sleep mode..."}
        
        elif command == 'lock':
            if system == 'Windows':
                os.system('rundll32.exe user32.dll,LockWorkStation')
            elif system == 'Linux':
                os.system('xdg-screensaver lock')
            return {"status": "ok", "message": "Screen locked"}
        
        # Timer Commands
        elif command == 'timer_shutdown':
            minutes = data.get('minutes', 60)
            if system == 'Windows':
                seconds = minutes * 60
                os.system(f'shutdown /s /t {seconds}')
            elif system == 'Linux':
                os.system(f'shutdown -h +{minutes}')
            PCControlHandler.shutdown_time = datetime.now() + timedelta(minutes=minutes)
            return {"status": "ok", "message": f"Shutdown scheduled in {minutes} minutes"}
        
        elif command == 'browse_limit':
            minutes = data.get('minutes', 60)
            if system == 'Windows':
                seconds = minutes * 60
                os.system(f'shutdown /s /t {seconds}')
            PCControlHandler.shutdown_time = datetime.now() + timedelta(minutes=minutes)
            return {"status": "ok", "message": f"Browse limit set to {minutes} minutes"}
        
        elif command == 'cancel_timer':
            if system == 'Windows':
                os.system('shutdown /a')
            elif system == 'Linux':
                os.system('shutdown -c')
            PCControlHandler.shutdown_time = None
            return {"status": "ok", "message": "Timer cancelled"}
        
        elif command == 'check_timer':
            if PCControlHandler.shutdown_time:
                remaining = PCControlHandler.shutdown_time - datetime.now()
                minutes = int(remaining.total_seconds() / 60)
                return {"status": "ok", "message": f"Time remaining: {minutes} minutes"}
            return {"status": "ok", "message": "No timer active"}
        
        # Process Commands
        elif command == 'get_processes':
            processes = []
            for proc in psutil.process_iter(['name']):
                try:
                    processes.append(proc.info['name'])
                except:
                    pass
            return {"status": "ok", "processes": list(set(processes))[:50]}
        
        elif command == 'kill_process':
            process_name = data.get('process', '')
            killed = False
            for proc in psutil.process_iter(['name']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        proc.kill()
                        killed = True
                except:
                    pass
            if killed:
                return {"status": "ok", "message": f"Closed {process_name}"}
            return {"status": "error", "message": f"Process {process_name} not found"}
        
        # Browser Commands
        elif command == 'close_chrome':
            return self.kill_browser('chrome')
        elif command == 'close_edge':
            return self.kill_browser('msedge')
        elif command == 'close_firefox':
            return self.kill_browser('firefox')
        elif command == 'close_all_browsers':
            self.kill_browser('chrome')
            self.kill_browser('msedge')
            self.kill_browser('firefox')
            return {"status": "ok", "message": "All browsers closed"}
        
        # System Info
        elif command == 'get_info':
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            info = {
                "PC Name": platform.node(),
                "OS": f"{platform.system()} {platform.release()}",
                "CPU Usage": f"{cpu}%",
                "RAM Usage": f"{memory.percent}%",
                "Disk Usage": f"{disk.percent}%",
                "Uptime": self.get_uptime()
            }
            return {"status": "ok", "info": info}
        
        elif command == 'battery':
            try:
                battery = psutil.sensors_battery()
                if battery:
                    return {"status": "ok", "message": f"Battery: {battery.percent}% - {'Charging' if battery.power_plugged else 'Not Charging'}"}
                return {"status": "ok", "message": "No battery detected (Desktop PC)"}
            except:
                return {"status": "ok", "message": "Battery info not available"}
        
        # Volume Commands
        elif command == 'volume_up':
            if system == 'Windows':
                os.system('powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"')
            return {"status": "ok", "message": "Volume increased"}
        
        elif command == 'volume_down':
            if system == 'Windows':
                os.system('powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"')
            return {"status": "ok", "message": "Volume decreased"}
        
        elif command == 'mute':
            if system == 'Windows':
                os.system('powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"')
            return {"status": "ok", "message": "Mute toggled"}
        
        elif command == 'max_volume':
            if system == 'Windows':
                for _ in range(50):
                    os.system('powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"')
            return {"status": "ok", "message": "Volume set to maximum"}
        
        # Message Command
        elif command == 'send_message':
            message = data.get('message', 'Hello from Remote Controller!')
            style = data.get('style', 'normal')
            if system == 'Windows':
                self.show_custom_popup(message, style)
            return {"status": "ok", "message": "Message sent to PC"}
        
        return {"status": "error", "message": "Unknown command"}
    
    def kill_browser(self, browser_name):
        killed = False
        for proc in psutil.process_iter(['name']):
            try:
                if browser_name in proc.info['name'].lower():
                    proc.kill()
                    killed = True
            except:
                pass
        if killed:
            return {"status": "ok", "message": f"{browser_name.capitalize()} closed"}
        return {"status": "error", "message": f"{browser_name.capitalize()} not running"}
    
    def show_custom_popup(self, message, style='normal'):
        """Display a custom styled popup window on PC"""
        import threading
        
        def show_window():
            try:
                import tkinter as tk
                from tkinter import font
                
                # Style configurations
                styles = {
                    'normal': {
                        'bg': '#667eea',
                        'header_bg': '#764ba2',
                        'icon': '📱',
                        'title': 'Remote Controller Message'
                    },
                    'warning': {
                        'bg': '#f39c12',
                        'header_bg': '#e67e22',
                        'icon': '⚠️',
                        'title': 'Warning Message'
                    },
                    'urgent': {
                        'bg': '#e74c3c',
                        'header_bg': '#c0392b',
                        'icon': '🚨',
                        'title': 'URGENT MESSAGE'
                    },
                    'info': {
                        'bg': '#3498db',
                        'header_bg': '#2980b9',
                        'icon': 'ℹ️',
                        'title': 'Information'
                    }
                }
                
                current_style = styles.get(style, styles['normal'])
                
                # Create the popup window
                root = tk.Tk()
                root.title(current_style['title'])
                
                # Get screen dimensions
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                
                # Window size - larger for better visibility
                window_width = 600
                window_height = 350
                
                # Center the window
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                
                root.geometry(f"{window_width}x{window_height}+{x}+{y}")
                
                # Make it always on top and slightly transparent
                root.attributes('-topmost', True)
                root.attributes('-alpha', 0.98)
                
                # Remove window decorations for modern look
                root.overrideredirect(True)
                
                # Add rounded corners effect with border
                root.configure(bg=current_style['bg'])
                
                # Main container with padding
                main_frame = tk.Frame(root, bg=current_style['bg'])
                main_frame.pack(fill='both', expand=True, padx=3, pady=3)
                
                # Header Frame
                header_frame = tk.Frame(main_frame, bg=current_style['header_bg'], height=80)
                header_frame.pack(fill='x', padx=0, pady=0)
                header_frame.pack_propagate(False)
                
                # Icon (large emoji)
                icon_label = tk.Label(
                    header_frame,
                    text=current_style['icon'],
                    font=font.Font(size=36),
                    bg=current_style['header_bg'],
                    fg='white'
                )
                icon_label.pack(pady=(15, 5))
                
                # Title
                title_font = font.Font(family="Segoe UI", size=14, weight="bold")
                title_label = tk.Label(
                    header_frame,
                    text=current_style['title'],
                    font=title_font,
                    bg=current_style['header_bg'],
                    fg='white'
                )
                title_label.pack()
                
                # Message Frame
                message_frame = tk.Frame(main_frame, bg=current_style['bg'])
                message_frame.pack(fill='both', expand=True, padx=30, pady=30)
                
                # Message Text (larger font, better spacing)
                message_font = font.Font(family="Segoe UI", size=16, weight='normal')
                message_label = tk.Label(
                    message_frame,
                    text=message,
                    font=message_font,
                    bg=current_style['bg'],
                    fg='white',
                    wraplength=530,
                    justify='center'
                )
                message_label.pack(expand=True)
                
                # Button Frame
                button_frame = tk.Frame(main_frame, bg=current_style['bg'])
                button_frame.pack(fill='x', padx=30, pady=(0, 25))
                
                # OK Button (large and prominent)
                button_font = font.Font(family="Segoe UI", size=13, weight="bold")
                ok_button = tk.Button(
                    button_frame,
                    text="✓  Got it!",
                    font=button_font,
                    bg='white',
                    fg=current_style['bg'],
                    activebackground='#f0f0f0',
                    activeforeground=current_style['bg'],
                    relief='flat',
                    cursor='hand2',
                    padx=50,
                    pady=15,
                    command=root.destroy,
                    borderwidth=0
                )
                ok_button.pack()
                
                # Add hover effect
                def on_enter(e):
                    ok_button['bg'] = '#f8f9fa'
                
                def on_leave(e):
                    ok_button['bg'] = 'white'
                
                ok_button.bind("<Enter>", on_enter)
                ok_button.bind("<Leave>", on_leave)
                
                # Add shadow effect simulation
                shadow_frame = tk.Frame(root, bg='black')
                shadow_frame.place(x=5, y=5, width=window_width, height=window_height)
                shadow_frame.lower()
                
                # Auto-close after 45 seconds
                root.after(45000, root.destroy)
                
                # Focus the window and make sure it's on top
                root.focus_force()
                root.lift()
                
                # Play notification sound based on style
                try:
                    import winsound
                    if style == 'urgent':
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    elif style == 'warning':
                        winsound.MessageBeep(winsound.MB_ICONWARNING)
                    else:
                        winsound.MessageBeep(winsound.MB_ICONINFORMATION)
                except:
                    pass
                
                # Blink for urgent messages
                if style == 'urgent':
                    def blink():
                        current_alpha = root.attributes('-alpha')
                        root.attributes('-alpha', 0.7 if current_alpha > 0.8 else 1.0)
                        root.after(500, blink)
                    blink()
                
                root.mainloop()
                
            except Exception as e:
                print(f"Error showing popup: {e}")
                # Fallback to default Windows message
                os.system(f'msg * "{message}"')
        
        # Run in separate thread so it doesn't block the server
        thread = threading.Thread(target=show_window, daemon=True)
        thread.start()
    
    def get_uptime(self):
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            hours = int(uptime.total_seconds() / 3600)
            return f"{hours} hours"
        except:
            return "Unknown"
    
    def log_message(self, format, *args):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{self.address_string()}] {format % args}")

def run_server(port=8080):
    # Load HTML file
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            PCControlHandler.HTML_CONTENT = f.read()
            # Update the HTML to connect to localhost automatically
            PCControlHandler.HTML_CONTENT = PCControlHandler.HTML_CONTENT.replace(
                'value=""',
                f'value="' + get_local_ip() + '"'
            )
    except FileNotFoundError:
        print("WARNING: index.html not found in current directory")
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, PCControlHandler)
    
    local_ip = get_local_ip()
    
    print("=" * 60)
    print("🖥️  PC REMOTE CONTROL SERVER")
    print("=" * 60)
    print(f"Server running on port: {port}")
    print(f"PC Name: {platform.node()}")
    print(f"System: {platform.system()} {platform.release()}")
    print("=" * 60)
    print("📱 ACCESS FROM YOUR PHONE:")
    print(f"   Open browser and go to: http://{local_ip}:{port}")
    print("=" * 60)
    print("💡 TIP: Add to Home Screen for app-like experience!")
    print("=" * 60)
    print("Press Ctrl+C to stop the server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped.")

def get_local_ip():
    """Get the local IP address of this machine"""
    import socket
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

if __name__ == '__main__':
    # Check if psutil is installed
    try:
        import psutil
    except ImportError:
        print("ERROR: psutil module not found!")
        print("Please install it using: pip install psutil")
        input("Press Enter to exit...")
        exit(1)
    
    run_server(8080)