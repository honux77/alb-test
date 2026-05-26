# ALB 테스트용 웹 앱

AWS Application Load Balancer 및 오토 스케일링 동작을 검증하기 위한 간단한 Flask 웹 앱입니다.

## 기능

- JWT 로그인 (닉네임만 입력, 패스워드 불필요)
- 현재 EC2 인스턴스 ID 표시
- 현재 접속 중인 사용자 목록 표시
- 전체 및 코어별 CPU 사용량 실시간 표시 (3초 갱신)
- CPU 부하 주기 버튼 (70% 수준, 5분간 유지)
- 부하 중지 버튼

## 환경

- OS: Amazon Linux 2023
- Python: 3.9
- nginx: 1.30

---

## 1. EC2 인스턴스 준비

### 인스턴스 생성 시 설정

| 항목 | 값 |
|---|---|
| AMI | Amazon Linux 2023 |
| 인스턴스 타입 | t2.micro 이상 |
| 키 페어 | 생성 또는 기존 키 사용 |
| 보안 그룹 | 아래 인바운드 규칙 참고 |

### 보안 그룹 인바운드 규칙

| 포트 | 프로토콜 | 소스 | 용도 |
|---|---|---|---|
| 22 | TCP | 내 IP 또는 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP (nginx) |

> 개발·테스트 중에만 5000 포트를 직접 열어 쓸 경우 5000/TCP도 추가합니다.

### AWS CLI로 보안 그룹 포트 열기

```bash
# 보안 그룹 ID 확인
SG_ID=$(aws ec2 describe-instances --instance-ids <instance-id> \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)

# 80 포트 오픈
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
```

---

## 2. SSH 접속

### 키 페어를 SSM Parameter Store에서 가져오는 경우

EC2 키 페어를 SSM Parameter Store에 저장해 둔 경우 아래 명령으로 로컬에 꺼낼 수 있습니다.

```bash
aws ssm get-parameter \
  --name '/ec2/keypair/<key-id>' \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text > ~/.ssh/mykey.pem

chmod 600 ~/.ssh/mykey.pem
```

> AWS 콘솔 → Systems Manager → Parameter Store에서 키 이름을 확인합니다.

### SSH 접속

```bash
ssh -i ~/.ssh/mykey.pem ec2-user@<public-ip>
```

### EC2 Instance Connect 사용 (키 없는 경우)

```bash
# 로컬 공개 키를 60초간 임시 등록
aws ec2-instance-connect send-ssh-public-key \
  --instance-id <instance-id> \
  --instance-os-user ec2-user \
  --ssh-public-key file://~/.ssh/id_ed25519.pub

# 바로 접속 (60초 이내)
ssh -i ~/.ssh/id_ed25519 ec2-user@<public-ip>
```

---

## 3. 앱 배포

### 3-1. pip 설치

Amazon Linux 2023에는 pip가 기본 포함되지 않으므로 먼저 설치합니다.

```bash
sudo yum install -y python3-pip
```

### 3-2. 앱 파일 전송

로컬에서 rsync로 전송합니다.

```bash
rsync -av -e "ssh -i ~/.ssh/mykey.pem" \
  ./app/ \
  ec2-user@<public-ip>:~/app/
```

### 3-3. 의존성 설치

```bash
ssh -i ~/.ssh/mykey.pem ec2-user@<public-ip>
cd ~/app
pip3 install -r requirements.txt
```

### 3-4. 앱 실행 (백그라운드)

```bash
nohup python3 app.py > ~/app/app.log 2>&1 &
```

로그 확인:

```bash
tail -f ~/app/app.log
```

앱 중지:

```bash
pkill -f 'python3 app.py'
```

> 기본 포트는 `5000`입니다. 환경변수 `PORT`로 변경할 수 있습니다.
> ```bash
> PORT=8080 nohup python3 app.py > ~/app/app.log 2>&1 &
> ```

---

## 4. nginx 리버스 프록시 설정 (80 포트 연동)

### 4-1. nginx 설치

```bash
sudo yum install -y nginx
```

### 4-2. 프록시 설정 파일 작성

```bash
sudo tee /etc/nginx/conf.d/flask.conf > /dev/null << 'EOF'
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
```

### 4-3. 설정 검증 및 nginx 시작

```bash
sudo nginx -t
sudo systemctl enable --now nginx
```

이후 재부팅 시에도 nginx가 자동으로 시작됩니다.

### 4-4. 동작 확인

```bash
curl http://<public-ip>/instance-id
# {"instance_id": "i-xxxxxxxxxxxxxxxxx"}
```

---

## 5. API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 메인 페이지 |
| POST | `/login` | 로그인 (body: `{"nickname": "이름"}`) |
| POST | `/logout` | 로그아웃 (Authorization 헤더 필요) |
| GET | `/instance-id` | EC2 인스턴스 ID |
| GET | `/users` | 현재 접속 중인 사용자 목록 |
| GET | `/cpu` | 전체 및 코어별 CPU 사용량 |
| POST | `/stress` | CPU 부하 시작 (70%, 5분) |
| POST | `/stress/stop` | CPU 부하 중지 |

### `/cpu` 응답 예시

```json
{
  "total": 68.5,
  "per_core": [71.2, 65.8]
}
```

---

## 6. 재배포 절차

코드 수정 후 재배포할 때는 아래 순서로 진행합니다.

```bash
# 1. 파일 전송
rsync -av -e "ssh -i ~/.ssh/mykey.pem" ./app/ ec2-user@<public-ip>:~/app/

# 2. 앱 재시작
ssh -i ~/.ssh/mykey.pem ec2-user@<public-ip> \
  "pkill -f 'python3 app.py'; sleep 1; cd ~/app && nohup python3 app.py > ~/app/app.log 2>&1 &"
```

nginx는 앱 서버와 별개로 계속 실행 중이므로 재시작 불필요합니다.
