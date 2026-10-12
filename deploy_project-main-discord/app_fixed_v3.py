import os
import sys
import subprocess
import uuid
import traceback
from datetime import datetime, timedelta
from functools import wraps
import threading

# [자동 설치 기능] 필요한 패키지가 없으면 자동으로 설치합니다.
def install_dependencies():
    packages = ["supabase", "flask", "apscheduler"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            print(f"🚀 {package} 패키지가 없습니다. 자동 설치를 시작합니다...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except Exception as e:
                print(f"❌ {package} 설치 실패: {e}")

# 앱 시작 전 실행
install_dependencies()

from flask import Flask, render_template, request, url_for, redirect, session, jsonify, make_response
from supabase import create_client, Client
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ✅ 관리자 비밀 열쇠 (URL 뒤에 ?key=mykey 형식으로 사용)
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

# ✅ Supabase 설정
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
BUCKET_NAME = "photos"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ✅ 관리자 권한 확인 함수
def check_admin_access():
    return request.args.get('key') == ADMIN_KEY

# ✅ 라이선스 만료 여부 확인 함수 (개선된 버전)
def is_license_expired(expiry_date_str):
    if not expiry_date_str or str(expiry_date_str).strip() in ["무제한", ""]:
        return False
    
    try:
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d'
        ]
        
        expiry_date_str = str(expiry_date_str).strip()
        now = datetime.now()
        
        for fmt in date_formats:
            try:
                expiry_datetime = datetime.strptime(expiry_date_str, fmt)
                if expiry_datetime <= now:
                    return True
                else:
                    return False
            except ValueError:
                continue
        return False
    except Exception as e:
        print(f"라이선스 확인 오류: {e}")
        return False

# ✅ 만료된 사용자 자동 삭제 함수
def delete_expired_users():
    try:
        print("[자동 정리] 만료된 사용자 조회 중...")
        res = supabase.table("users").select("*").execute()
        if not res.data:
            return
        
        deleted_count = 0
        for user in res.data:
            expiry_date = user.get('expiredate', '')
            if is_license_expired(expiry_date):
                try:
                    photo_url = user.get('얼굴사진', '')
                    if photo_url and BUCKET_NAME in photo_url:
                        try:
                            filename = photo_url.split('/')[-1]
                            supabase.storage.from_(BUCKET_NAME).remove([filename])
                        except: pass
                    
                    supabase.table("users").delete().eq("id", user.get('id')).execute()
                    deleted_count += 1
                except Exception as e:
                    print(f"  [에러] 사용자 삭제 실패: {e}")
        
        if deleted_count > 0:
            print(f"[자동 정리] 총 {deleted_count}명의 만료된 사용자가 삭제되었습니다.")
    except Exception as e:
        print(f"[자동 정리] 오류 발생: {e}")

# ✅ 스케줄러 초기화
scheduler = BackgroundScheduler()
scheduler_started = False

def start_scheduler():
    global scheduler_started
    if not scheduler_started:
        try:
            scheduler.add_job(
                func=delete_expired_users,
                trigger=IntervalTrigger(hours=1),
                id='delete_expired_users',
                name='만료된 사용자 자동 삭제',
                replace_existing=True
            )
            scheduler.start()
            scheduler_started = True
            print("✅ 자동 정리 스케줄러가 시작되었습니다. (1시간 주기)")
        except Exception as e:
            print(f"❌ 스케줄러 시작 실패: {e}")

@app.route('/')
def index():
    if check_admin_access():
        return render_template('register.html', admin_key=ADMIN_KEY)
    return '''
        <div style="text-align:center; margin-top:100px; font-family:sans-serif; color:#666;">
            <img src="https://cdn-icons-png.flaticon.com/512/2592/2592261.png" width="100" style="opacity:0.5;">
            <h2>서비스 점검 중입니다.</h2>
            <p>현재 시스템 최적화 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.</p>
        </div>
    ''', 200

@app.route('/api/users')
def get_users():
    if not check_admin_access():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        res = supabase.table("users").select("*").order("id", desc=True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/register', methods=['POST'])
def register():
    try:
        name = request.form.get('name')
        num = request.form.get('num')
        juso = request.form.get('juso')
        detail_juso = request.form.get('detail_juso', '')
        make = request.form.get('make')
        jiname = request.form.get('jiname')
        expiry_date = request.form.get('expiry_date', '').replace('T', ' ')
        if not expiry_date: expiry_date = '무제한'
        
        license_key = request.form.get('license_key', '')
        if not license_key: license_key = str(uuid.uuid4())[:12]

        photo = request.files.get('photo')
        imgurl = ""
        if photo and photo.filename:
            file_ext = os.path.splitext(photo.filename)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            file_data = photo.read()
            supabase.storage.from_(BUCKET_NAME).upload(
                path=filename,
                file=file_data,
                file_options={"content-type": photo.content_type}
            )
            imgurl = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"

        query = str(uuid.uuid4())[:8]

        data = {
            "query": query, "이름": name, "주민등록번호": num, "집주소": juso,
            "상세주소": detail_juso, "주민등록일자": make, "지역": jiname,
            "얼굴사진": imgurl, "expiredate": expiry_date, "license_key": license_key
        }

        supabase.table("users").insert(data).execute()
        personal_link = f"{request.host_url}{query}"
        return redirect(personal_link)
    except Exception as e:
        traceback.print_exc()
        return f"등록 실패: {str(e)}", 500

@app.route('/delete_by_license', methods=['POST'])
def delete_by_license():
    if not check_admin_access():
        return "Unauthorized", 403
    try:
        key = request.form.get('license_key')
        user_res = supabase.table("users").select("얼굴사진").eq("license_key", key).execute()
        if user_res.data:
            for user in user_res.data:
                photo_url = user.get('얼굴사진')
                if photo_url and BUCKET_NAME in photo_url:
                    filename = photo_url.split('/')[-1]
                    try: supabase.storage.from_(BUCKET_NAME).remove([filename])
                    except: pass
        supabase.table("users").delete().eq("license_key", key).execute()
        return "Deleted", 200
    except Exception as e:
        return str(e), 500

@app.route('/extend_license', methods=['POST'])
def extend_license():
    if not check_admin_access():
        return "Unauthorized", 403
    try:
        key = request.form.get('license_key')
        new_expiry = request.form.get('expiry_date', '').replace('T', ' ')
        if not new_expiry:
            return "Expiry date is required", 400
        
        supabase.table("users").update({"expiredate": new_expiry}).eq("license_key", key).execute()
        return "Extended", 200
    except Exception as e:
        return str(e), 500

@app.route('/<query>')
def show_id(query):
    try:
        if query == 'favicon.ico': return '', 204
        res = supabase.table("users").select("*").eq("query", query).limit(1).execute()
        if not res.data:
            return "<h1>❌ 삭제되었거나 존재하지 않는 신분증입니다.</h1>", 404
        user = res.data[0]
        exp = user.get('expiredate', '')
        
        if is_license_expired(exp):
            try:
                photo_url = user.get('얼굴사진', '')
                if photo_url and BUCKET_NAME in photo_url:
                    try:
                        filename = photo_url.split('/')[-1]
                        supabase.storage.from_(BUCKET_NAME).remove([filename])
                    except: pass
                supabase.table("users").delete().eq("query", query).execute()
            except: pass
            
            return '''
                <html><head><meta charset="UTF-8"><title>라이선스 만료</title></head>
                <body style="display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f0f2f5;font-family:sans-serif;">
                <div style="background:white;padding:50px;border-radius:15px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                <h1 style="color:#e74c3c;">⚠️ 라이선스 만료</h1>
                <p>이 신분증의 이용 기간이 만료되어 자동으로 삭제되었습니다.</p>
                <p>만료일자: <b>''' + str(exp) + '''</b></p>
                </div></body></html>
            ''', 403
        
        return render_template('sex.html', 
                             name=user.get('이름', ''), date=user.get('주민등록일자', ''), 
                             juso=user.get('집주소', ''), detail_juso=user.get('상세주소', ''), 
                             imgurl=user.get('얼굴사진', ''), num=user.get('주민등록번호', ''), 
                             make=user.get('주민등록일자', ''), jiname=user.get('지역', ''), 
                             query=query)
    except Exception as e:
        return f"조회 실패: {str(e)}", 500

@app.route('/qr_check/<query>')
def qr_check(query):
    try:
        res = supabase.table("users").select("*").eq("query", query).limit(1).execute()
        if not res.data:
            return "<h1>❌ 유효하지 않은 QR 코드입니다.</h1>", 404
        
        user = res.data[0]
        exp = user.get('expiredate', '')
        
        if is_license_expired(exp):
            try:
                photo_url = user.get('얼굴사진', '')
                if photo_url and BUCKET_NAME in photo_url:
                    try:
                        filename = photo_url.split('/')[-1]
                        supabase.storage.from_(BUCKET_NAME).remove([filename])
                    except: pass
                supabase.table("users").delete().eq("query", query).execute()
            except: pass
            return "<h1>⚠️ 라이선스 만료로 삭제되었습니다.</h1>", 403
        
        jumin = user.get('주민등록번호', '000000-0000000')
        birth_raw = jumin.split('-')[0]
        gender_code = jumin.split('-')[1][0] if '-' in jumin and len(jumin.split('-')[1]) > 0 else '1'
        year_prefix = "19" if gender_code in ['1', '2', '5', '6'] else "20"
        birth = f"{year_prefix}{birth_raw[0:2]}.{birth_raw[2:4]}.{birth_raw[4:6]}"

        return render_template('qr_check.html', name=user.get('이름', ''), birth=birth, jiname=user.get('지역', ''), imgurl=user.get('얼굴사진', ''))
    except Exception as e:
        return f"검증 실패: {str(e)}", 500

# 앱 컨텍스트 내에서 스케줄러 시작
with app.app_context():
    start_scheduler()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
