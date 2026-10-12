from flask import Flask, render_template, request, url_for, redirect, session, jsonify, make_response
import os

app = Flask(__name__)

@app.route('/qr_check/<query>')
def qr_check(query):
    # 테스트용 가상 데이터
    user = {
        '이름': '홍길동',
        '주민등록번호': '900101-1234567',
        '지역': '서울특별시',
        '얼굴사진': 'https://via.placeholder.com/150'
    }
    birth = "1990.01.01"
    return render_template('qr_check.html', 
                         name=user.get('이름', ''), 
                         birth=birth, 
                         jiname=user.get('지역', ''), 
                         imgurl=user.get('얼굴사진', ''))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
