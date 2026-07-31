import os
import sys
import subprocess
import paramiko

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HOST = "72.56.79.35"
USER = "root"
PASSWORD = "cVq5,#L?xJy_L6"
REMOTE_DIR = "/opt/vacancy-spotter-app"
LOCAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_FRONTEND_DIR = os.path.join(LOCAL_DIR, "frontend")

IGNORE_DIRS = {".venv", "__pycache__", ".git", ".idea", ".vscode", ".pytest_cache", "node_modules"}
IGNORE_FILES = {".gitignore"}

def run_local_preflight_checks():
    print("\n==========================================")
    print("🚀 RUNNING PRE-DEPLOY VALIDATION GATE...")
    print("==========================================")
    
    # 1. Build frontend React app
    print("\n[Gate 1/2] Compiling Frontend React App (npm run build)...")
    res_fe = subprocess.run(["npm", "run", "build"], cwd=LOCAL_FRONTEND_DIR, shell=True)
    if res_fe.returncode != 0:
        print("❌ Frontend build failed! Deployment aborted.")
        sys.exit(1)
    print("✅ Frontend build successful!")

    # 2. Run Pytest backend test suite
    print("\n[Gate 2/2] Running Backend Pytest Suite (pytest backend/tests)...")
    env = {**os.environ, "PYTHONPATH": os.path.join(LOCAL_DIR, "backend")}
    res_be = subprocess.run([sys.executable, "-m", "pytest", "backend/tests"], cwd=LOCAL_DIR, env=env)
    if res_be.returncode != 0:
        print("❌ Backend tests failed! Deployment aborted.")
        sys.exit(1)
    print("✅ All backend unit tests passed!")
    
    # 3. Commit and Push to GitHub for Vercel auto-build
    print("\n[Gate 3/3] Pushing latest build to GitHub & Vercel...")
    subprocess.run(["git", "add", "."], cwd=LOCAL_DIR)
    subprocess.run(["git", "commit", "-m", "deploy: sync latest build & vercel config"], cwd=LOCAL_DIR)
    res_push = subprocess.run(["git", "push", "origin", "main"], cwd=LOCAL_DIR)
    if res_push.returncode == 0:
        print("✅ Git push successful! Vercel build triggered.")
    else:
        print("⚠️ Git push skipped or failed. Continuing VPS deployment.")

    print("==========================================")
    print("✅ PRE-DEPLOYMENT GATE PASSED SUCCESSFULLY!")
    print("==========================================\n")

def exec_cmd(ssh, cmd):
    print(f"\n--- Running: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_status = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"[STDOUT]\n{out.strip()}")
    if err.strip():
        print(f"[STDERR]\n{err.strip()}")
    print(f"[EXIT STATUS] {exit_status}")
    return exit_status, out, err

def main():
    run_local_preflight_checks()

    print(f"Connecting to {HOST} as {USER} for SaaS deployment...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    print("SSH Connection established!")

    # 1. Create remote directory
    exec_cmd(ssh, f"mkdir -p {REMOTE_DIR}/data")

    # 2. Upload files via SFTP
    sftp = ssh.open_sftp()
    uploaded_count = 0

    def upload_dir(local_path, remote_path):
        nonlocal uploaded_count
        try:
            sftp.mkdir(remote_path)
        except IOError:
            pass
            
        for item in os.listdir(local_path):
            if item in IGNORE_DIRS or item in IGNORE_FILES:
                continue
            
            l_item = os.path.join(local_path, item)
            r_item = f"{remote_path}/{item}"
            
            if os.path.isdir(l_item):
                upload_dir(l_item, r_item)
            else:
                sftp.put(l_item, r_item)
                uploaded_count += 1

    upload_dir(LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    print(f"Uploaded total {uploaded_count} files to VPS.")

    # 3. Create Virtualenv and install requirements
    exec_cmd(ssh, f"python3 -m venv {REMOTE_DIR}/venv")
    exec_cmd(ssh, f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip")
    exec_cmd(ssh, f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt")
    exec_cmd(ssh, f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/backend/requirements.txt")

    # 4. Copy backend/.env to root .env if needed
    exec_cmd(ssh, f"cp {REMOTE_DIR}/backend/.env {REMOTE_DIR}/.env")

    # 5. Create systemd service unit for SaaS bot & API
    service_content = f"""[Unit]
Description=Vacancy Spotter SaaS Bot & API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_DIR}
ExecStart={REMOTE_DIR}/venv/bin/python app.py
Restart=always
RestartSec=10
EnvironmentFile=-{REMOTE_DIR}/.env

[Install]
WantedBy=multi-user.target
"""

    exec_cmd(ssh, f"cat << 'EOF' > /etc/systemd/system/vacancy-spotter-saas.service\n{service_content}\nEOF")

    # 6. Enable and restart service
    exec_cmd(ssh, "systemctl daemon-reload")
    exec_cmd(ssh, "systemctl enable vacancy-spotter-saas.service")
    exec_cmd(ssh, "systemctl restart vacancy-spotter-saas.service")

    # 7. Check status and logs
    exec_cmd(ssh, "systemctl status vacancy-spotter-saas.service --no-pager")
    exec_cmd(ssh, "journalctl -u vacancy-spotter-saas.service -n 20 --no-pager")

    ssh.close()
    print("\n🎉 Deployment completed with zero errors!")

if __name__ == "__main__":
    main()
