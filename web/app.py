from flask import Flask, request, jsonify, render_template
import redis
import re
import os

app = Flask(__name__)

# 환경변수 불러오기
ACCESS_CODE = os.environ.get('ACCESS_CODE', '0000')
# 쉼표로 구분된 도메인 문자열을 리스트로 변환하고 공백 제거
ALLOWED_DOMAINS = [d.strip() for d in os.environ.get('ALLOWED_DOMAINS', 'example.com').split(',')]

r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

@app.route('/')
def index():
    # UI에 도메인 목록을 전달하여 선택할 수 있게 함
    return render_template('index.html', domains=ALLOWED_DOMAINS)

@app.route('/assign', methods=['POST'])
def assign():
    data = request.json
    
    # 1. Access Code 검증
    user_code = data.get('code')
    if user_code != ACCESS_CODE:
        return jsonify({'error': '액세스 코드가 올바르지 않습니다.'}), 403

    target_ip = data.get('ip')
    target_port = data.get('port')
    subdomain_part = data.get('subdomain')
    selected_domain = data.get('domain')
    duration = data.get('duration') # 숫자 (문자열일 수 있음)
    unit = data.get('unit') # 'hours' 또는 'days'

    # 2. 필수값 체크
    if not (target_ip and target_port and subdomain_part and selected_domain):
        return jsonify({'error': '필수 정보를 모두 입력해주세요.'}), 400

    # 3. 도메인 유효성 체크 (허용된 도메인 리스트에 있는지)
    if selected_domain not in ALLOWED_DOMAINS:
        return jsonify({'error': '허용되지 않은 도메인입니다.'}), 400

    # 4. 서브도메인 형식 체크
    if not re.match(r'^[a-z0-9-]+$', subdomain_part):
        return jsonify({'error': '서브도메인은 영문 소문자, 숫자, 하이픈만 가능합니다.'}), 400

    # 최종 호스트네임 생성 (예: sub.example.com)
    full_hostname = f"{subdomain_part}.{selected_domain}"

    # 5. 중복 체크
    if r.exists(full_hostname):
        return jsonify({'error': f"'{full_hostname}'은(는) 이미 사용 중입니다."}), 409

    # 6. 만료 시간 계산
    ex_seconds = None # 기본값: None (무제한)
    
    if duration and str(duration).strip(): # 값이 있을 때만 계산
        try:
            val = int(duration)
            if val > 0:
                if unit == 'days':
                    ex_seconds = val * 86400
                else: # hours
                    ex_seconds = val * 3600
        except ValueError:
            return jsonify({'error': '시간은 숫자만 입력해주세요.'}), 400

    # 7. Redis 저장 (Key: 전체 도메인)
    r.set(full_hostname, f"{target_ip}:{target_port}", ex=ex_seconds)

    expiry_msg = "무기한" if ex_seconds is None else f"{duration} {unit} 후 만료"
    
    return jsonify({
        'full_url': f"http://{full_hostname}",
        'expiry': expiry_msg
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
