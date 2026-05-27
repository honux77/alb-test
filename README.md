# ALB 테스트용 웹 앱

AWS Application Load Balancer 및 오토 스케일링 동작을 검증하기 위한 간단한 Flask 웹 앱입니다.

## 기능

- JWT 로그인 (닉네임만 입력, 패스워드 불필요, 중복 시 `_XXX` 자동 부여)
- 현재 EC2 인스턴스 ID 표시 (로컬 실행 시 `LOCAL-{호스트명}`)
- 현재 접속 중인 사용자 목록 표시
- 전체 및 코어별 CPU 사용량 실시간 표시 (3초 갱신)
- CPU 부하 주기 버튼 (70% 수준, 5분간 유지)
- 부하 중지 버튼

## 환경

- OS: Amazon Linux 2023
- Python 3, nginx

---

## 로컬 실행

```bash
cd app
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
python app.py
# 포트 변경: PORT=8080 python app.py
```

브라우저에서 http://localhost:5000 으로 접속합니다.

---

## EC2 배포

`create-ec2-deploy.sh`를 실행하면 인스턴스 생성부터 앱 기동까지 자동으로 처리됩니다.

```bash
bash create-ec2-deploy.sh
```

스크립트가 완료되면 슬랙으로 인스턴스 ID와 접속 URL이 전송됩니다.  
앱 기동까지 약 1~2분 소요됩니다 (user-data 실행 중).

### 보안 그룹 인바운드 규칙

| 포트 | 용도 |
|---|---|
| 22 | SSH |
| 80 | HTTP (nginx) |

---

## SSH 접속

```bash
ssh -i ~/.ssh/<key-name>.pem ec2-user@<public-ip>
```

---

## 업데이트 (코드 수정 후 반영)

```bash
# 1. 변경사항 push
git push origin main

# 2. 인스턴스에서 pull 및 재시작
ssh -i ~/.ssh/<key-name>.pem ec2-user@<public-ip> \
  "cd /opt/alb-test && git pull && sudo systemctl restart alb-test"
```

---

## API 엔드포인트

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
