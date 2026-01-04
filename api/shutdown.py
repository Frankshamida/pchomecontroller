import os
import platform
import json
import psutil
from datetime import datetime, timedelta

def handler(request, response):
    if request.method == 'POST':
        try:
            data = request.json()
            command = data.get('command', '')
            result = handle_command(command, data)
            response.status_code = 200
            response.headers['Content-Type'] = 'application/json'
            response.body = json.dumps(result)
        except Exception as e:
            response.status_code = 500
            response.body = json.dumps({"status": "error", "message": str(e)})
    else:
        response.status_code = 405
        response.body = json.dumps({"status": "error", "message": "Method not allowed"})

def handle_command(command, data):
    system = platform.system()
    if command == 'shutdown':
        return {"status": "ok", "message": "Shutdown command received (not executed in cloud)"}
    elif command == 'restart':
        return {"status": "ok", "message": "Restart command received (not executed in cloud)"}
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
        }
        return {"status": "ok", "info": info}
    return {"status": "error", "message": "Unknown command or not supported on Vercel"}
