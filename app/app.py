from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
import socket
import psutil
import multiprocessing
import time
import urllib.request
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key'
jwt = JWTManager(app)

# 접속자 관리
connected_users = set()
# 부하 상태
stress_active = False
stress_processes = []

def get_instance_id():
    try:
        # IMDSv2: 먼저 토큰 발급
        token_req = urllib.request.Request(
            'http://169.254.169.254/latest/api/token',
            method='PUT',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'}
        )
        with urllib.request.urlopen(token_req, timeout=1) as r:
            token = r.read().decode()
        id_req = urllib.request.Request(
            'http://169.254.169.254/latest/meta-data/instance-id',
            headers={'X-aws-ec2-metadata-token': token}
        )
        with urllib.request.urlopen(id_req, timeout=1) as r:
            return r.read().decode()
    except Exception:
        return f"LOCAL-{socket.gethostname()}"

def get_cpu_usage():
    overall = psutil.cpu_percent(interval=0.3)
    per_core = psutil.cpu_percent(percpu=True, interval=0.3)
    return {'total': overall, 'per_core': per_core}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    nickname = request.json.get('nickname', None)
    if not nickname:
        return jsonify({'msg': '닉네임 필요'}), 400
    original = nickname
    while nickname in connected_users:
        nickname = f"{original}_{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
    access_token = create_access_token(identity=nickname)
    connected_users.add(nickname)
    return jsonify(access_token=access_token, nickname=nickname)

@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    nickname = get_jwt_identity()
    connected_users.discard(nickname)
    return jsonify({'msg': '로그아웃 완료'})

@app.route('/instance-id')
def instance_id():
    return jsonify({'instance_id': get_instance_id()})

@app.route('/users')
def users():
    return jsonify({'users': list(connected_users)})

@app.route('/cpu')
def cpu():
    return jsonify(get_cpu_usage())

def _cpu_worker():
    target = 0.70
    interval = 0.05  # 50ms 단위로 제어 (정밀도 향상)
    end_time = time.time() + 300
    while time.time() < end_time:
        deadline = time.perf_counter() + interval * target
        while time.perf_counter() < deadline:
            pass
        time.sleep(interval * (1 - target))

@app.route('/stress', methods=['POST'])
def stress():
    global stress_active, stress_processes
    if not stress_active:
        stress_active = True
        cpu_count = multiprocessing.cpu_count()
        for _ in range(cpu_count):
            p = multiprocessing.Process(target=_cpu_worker, daemon=True)
            p.start()
            stress_processes.append(p)
    return jsonify({'msg': 'CPU 부하 시작'})

@app.route('/stress/stop', methods=['POST'])
def stop_stress():
    global stress_active, stress_processes
    stress_active = False
    for p in stress_processes:
        p.terminate()
        p.join(timeout=1)
    stress_processes = []
    return jsonify({'msg': 'CPU 부하 중지'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
