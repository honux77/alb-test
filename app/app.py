from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
import socket
import psutil
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key'
jwt = JWTManager(app)

# 접속자 관리
connected_users = set()
# 부하 상태
stress_active = False
stress_thread = None

# 인스턴스 ID (EC2 환경이면 metadata에서 가져올 수 있음, 여기선 hostname 사용)
def get_instance_id():
    return socket.gethostname()

def get_cpu_usage():
    return psutil.cpu_percent(interval=1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    nickname = request.json.get('nickname', None)
    if not nickname:
        return jsonify({'msg': '닉네임 필요'}), 400
    access_token = create_access_token(identity=nickname)
    connected_users.add(nickname)
    return jsonify(access_token=access_token)

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
    return jsonify({'cpu': get_cpu_usage()})

# 부하를 주는 함수
def stress_cpu():
    global stress_active
    end_time = time.time() + 300  # 5분
    while stress_active and time.time() < end_time:
        # CPU를 70% 정도로 사용하도록 busy-wait
        start = time.time()
        while (time.time() - start) < 0.7:
            pass
        time.sleep(0.3)
    stress_active = False

@app.route('/stress', methods=['POST'])
def stress():
    global stress_active, stress_thread
    if not stress_active:
        stress_active = True
        stress_thread = threading.Thread(target=stress_cpu)
        stress_thread.start()
    return jsonify({'msg': 'CPU 부하 시작'})

@app.route('/stress/stop', methods=['POST'])
def stop_stress():
    global stress_active
    stress_active = False
    return jsonify({'msg': 'CPU 부하 중지'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
