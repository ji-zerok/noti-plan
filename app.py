from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from sqlalchemy import func
import os

# 한국 시간 헬퍼 함수
def kst_now():
    return datetime.utcnow() + timedelta(hours=9)

app = Flask(__name__)

# PostgreSQL (production) or SQLite (local development)
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render PostgreSQL URL fix (postgres:// -> postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///noti_plan.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'noti_plan_secret_key_2848'
db = SQLAlchemy(app)

ADMIN_PASSWORD = '2848'

# 모델 정의
class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=kst_now)
    services = db.relationship('Service', backref='organization', lazy=True)
    quotas = db.relationship('MonthlyQuota', backref='organization', lazy=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    manager_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=kst_now)
    requests = db.relationship('SendRequest', backref='service', lazy=True)

class MonthlyQuota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    channel = db.Column(db.String(20), nullable=False, default='naver')  # naver, payco, talktalk
    total_quota = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=kst_now)

    __table_args__ = (db.UniqueConstraint('organization_id', 'year_month', 'channel'),)

class SendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    send_date = db.Column(db.Date, nullable=False)
    send_time = db.Column(db.String(5))  # HH:MM
    channel = db.Column(db.String(20), nullable=False, default='naver')  # naver, payco, talktalk
    campaign_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=kst_now)
    updated_at = db.Column(db.DateTime, default=kst_now, onupdate=kst_now)

# 프리징 관리
class MonthlyFreeze(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year_month = db.Column(db.String(7), nullable=False, unique=True)  # YYYY-MM
    is_frozen = db.Column(db.Boolean, default=False)
    frozen_at = db.Column(db.DateTime)
    frozen_by = db.Column(db.String(100))  # 관리자
    created_at = db.Column(db.DateTime, default=kst_now)

# 변경 요청
class ChangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    request_type = db.Column(db.String(20), nullable=False)  # add, modify, delete
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)

    # 기존 캠페인 (수정/삭제인 경우)
    original_request_id = db.Column(db.Integer, db.ForeignKey('send_request.id'))

    # 변경 내용
    send_date = db.Column(db.Date)
    send_time = db.Column(db.String(5))
    channel = db.Column(db.String(20))
    campaign_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer)

    # 요청 정보
    reason = db.Column(db.Text, nullable=False)  # 변경 사유
    requester_name = db.Column(db.String(100), nullable=False)  # 요청자

    # 처리 정보
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_memo = db.Column(db.Text)  # 관리자 메모
    processed_by = db.Column(db.String(100))  # 처리자
    processed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=kst_now)

    # Relationships
    service = db.relationship('Service', backref='change_requests')
    original_request = db.relationship('SendRequest', backref='change_requests', foreign_keys=[original_request_id])

# 관리자 로그인 페이지
@app.route('/')
@app.route('/admin/login')
def admin_login():
    return render_template('admin_login.html')

# 관리자 로그인 처리
@app.route('/api/admin/login', methods=['POST'])
def admin_login_process():
    data = request.json
    password = data.get('password')

    if password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '비밀번호가 올바르지 않습니다.'}), 401

# 관리자 로그아웃
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# 관리자 화면 - 조직별 물량 설정
@app.route('/admin')
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    organizations = Organization.query.all()
    return render_template('admin.html', organizations=organizations)

# 서비스 담당자 화면 - 물량 신청
@app.route('/request')
def request_page():
    organizations = Organization.query.all()
    return render_template('request.html', organizations=organizations)

# 달력 화면 - 물량 현황
@app.route('/calendar')
def calendar_page():
    organizations = Organization.query.all()
    return render_template('calendar.html', organizations=organizations)

# 변경 요청 화면
@app.route('/change-requests')
def change_requests_page():
    organizations = Organization.query.all()
    return render_template('change_requests.html', organizations=organizations)

# API: 조직별 월간 물량 설정
@app.route('/api/quota', methods=['POST'])
def set_quota():
    data = request.json
    organization_id = data.get('organization_id')
    year_month = data.get('year_month')
    channel = data.get('channel', 'naver')
    total_quota = data.get('total_quota')

    quota = MonthlyQuota.query.filter_by(
        organization_id=organization_id,
        year_month=year_month,
        channel=channel
    ).first()

    if quota:
        quota.total_quota = total_quota
    else:
        quota = MonthlyQuota(
            organization_id=organization_id,
            year_month=year_month,
            channel=channel,
            total_quota=total_quota
        )
        db.session.add(quota)

    db.session.commit()
    return jsonify({'success': True, 'message': '물량이 설정되었습니다.'})

# API: 조직별 월간 물량 조회
@app.route('/api/quota/<int:org_id>/<year_month>')
def get_quota(org_id, year_month):
    quota = MonthlyQuota.query.filter_by(
        organization_id=org_id,
        year_month=year_month
    ).first()

    if quota:
        return jsonify({
            'total_quota': quota.total_quota
        })
    return jsonify({'total_quota': 0})

# API: 전체 물량 목록 조회
@app.route('/api/quotas')
def get_all_quotas():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    year_month = request.args.get('year_month')
    channel = request.args.get('channel')

    query = db.session.query(
        MonthlyQuota,
        Organization.name
    ).join(Organization)

    if year_month:
        query = query.filter(MonthlyQuota.year_month == year_month)

    if channel:
        query = query.filter(MonthlyQuota.channel == channel)

    quotas = query.order_by(MonthlyQuota.year_month.desc(), MonthlyQuota.channel, Organization.name).all()

    return jsonify([{
        'id': quota.id,
        'organization_name': org_name,
        'organization_id': quota.organization_id,
        'year_month': quota.year_month,
        'channel': quota.channel,
        'total_quota': quota.total_quota,
        'created_at': quota.created_at.strftime('%Y-%m-%d %H:%M')
    } for quota, org_name in quotas])

# API: 물량 수정
@app.route('/api/quota/<int:quota_id>', methods=['PUT'])
def update_quota(quota_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    new_quota = data.get('total_quota')

    quota = MonthlyQuota.query.get(quota_id)
    if not quota:
        return jsonify({'success': False, 'message': '물량을 찾을 수 없습니다.'}), 404

    quota.total_quota = new_quota
    db.session.commit()

    return jsonify({'success': True, 'message': '물량이 수정되었습니다.'})

# API: 물량 삭제
@app.route('/api/quota/<int:quota_id>', methods=['DELETE'])
def delete_quota(quota_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    quota = MonthlyQuota.query.get(quota_id)
    if not quota:
        return jsonify({'success': False, 'message': '물량을 찾을 수 없습니다.'}), 404

    db.session.delete(quota)
    db.session.commit()

    return jsonify({'success': True, 'message': '물량이 삭제되었습니다.'})

# API: 특정 월의 전체 물량 복사
@app.route('/api/quotas/copy', methods=['POST'])
def copy_quotas():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    source_year_month = data.get('source_year_month')
    target_year_month = data.get('target_year_month')

    if not source_year_month or not target_year_month:
        return jsonify({'success': False, 'message': '원본 월과 대상 월을 선택해주세요.'}), 400

    if source_year_month == target_year_month:
        return jsonify({'success': False, 'message': '원본 월과 대상 월이 같을 수 없습니다.'}), 400

    # 원본 월의 물량 조회
    source_quotas = MonthlyQuota.query.filter_by(year_month=source_year_month).all()

    if not source_quotas:
        return jsonify({'success': False, 'message': '원본 월에 설정된 물량이 없습니다.'}), 404

    # 대상 월에 이미 존재하는 물량 확인
    existing_quotas = MonthlyQuota.query.filter_by(year_month=target_year_month).all()
    existing_org_ids = {q.organization_id for q in existing_quotas}

    copied_count = 0
    skipped_count = 0

    for source_quota in source_quotas:
        if source_quota.organization_id in existing_org_ids:
            skipped_count += 1
            continue

        new_quota = MonthlyQuota(
            organization_id=source_quota.organization_id,
            year_month=target_year_month,
            total_quota=source_quota.total_quota
        )
        db.session.add(new_quota)
        copied_count += 1

    db.session.commit()

    message = f'{copied_count}개 조직의 물량이 복사되었습니다.'
    if skipped_count > 0:
        message += f' ({skipped_count}개 조직은 이미 존재하여 건너뜀)'

    return jsonify({'success': True, 'message': message, 'copied_count': copied_count, 'skipped_count': skipped_count})

# API: 조직 추가
@app.route('/api/organization', methods=['POST'])
def add_organization():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    name = data.get('name')

    if not name:
        return jsonify({'success': False, 'message': '조직명을 입력하세요.'}), 400

    # 중복 체크
    existing = Organization.query.filter_by(name=name).first()
    if existing:
        return jsonify({'success': False, 'message': '이미 존재하는 조직명입니다.'}), 400

    org = Organization(name=name)
    db.session.add(org)
    db.session.commit()

    return jsonify({'success': True, 'message': '조직이 추가되었습니다.', 'id': org.id})

# API: 조직 수정
@app.route('/api/organization/<int:org_id>', methods=['PUT'])
def update_organization(org_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    name = data.get('name')

    if not name:
        return jsonify({'success': False, 'message': '조직명을 입력하세요.'}), 400

    org = Organization.query.get(org_id)
    if not org:
        return jsonify({'success': False, 'message': '조직을 찾을 수 없습니다.'}), 404

    # 중복 체크 (자신 제외)
    existing = Organization.query.filter(Organization.name == name, Organization.id != org_id).first()
    if existing:
        return jsonify({'success': False, 'message': '이미 존재하는 조직명입니다.'}), 400

    org.name = name
    db.session.commit()

    return jsonify({'success': True, 'message': '조직이 수정되었습니다.'})

# API: 조직 삭제
@app.route('/api/organization/<int:org_id>', methods=['DELETE'])
def delete_organization(org_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    org = Organization.query.get(org_id)
    if not org:
        return jsonify({'success': False, 'message': '조직을 찾을 수 없습니다.'}), 404

    # 해당 조직의 서비스가 있는지 확인
    services = Service.query.filter_by(organization_id=org_id).count()
    if services > 0:
        return jsonify({'success': False, 'message': f'이 조직에 {services}개의 서비스가 있습니다. 먼저 서비스를 삭제해주세요.'}), 400

    # 물량 정보가 있는지 확인
    quotas = MonthlyQuota.query.filter_by(organization_id=org_id).count()
    if quotas > 0:
        return jsonify({'success': False, 'message': f'이 조직에 {quotas}개의 물량 정보가 있습니다. 먼저 물량 정보를 삭제해주세요.'}), 400

    db.session.delete(org)
    db.session.commit()

    return jsonify({'success': True, 'message': '조직이 삭제되었습니다.'})

# API: 서비스 추가
@app.route('/api/service', methods=['POST'])
def add_service():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    name = data.get('name')
    organization_id = data.get('organization_id')
    manager_name = data.get('manager_name', '')

    if not name or not organization_id:
        return jsonify({'success': False, 'message': '필수 항목을 입력하세요.'}), 400

    service = Service(name=name, organization_id=organization_id, manager_name=manager_name)
    db.session.add(service)
    db.session.commit()

    return jsonify({'success': True, 'message': '서비스가 추가되었습니다.', 'id': service.id})

# API: 서비스 수정
@app.route('/api/service/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    name = data.get('name')
    organization_id = data.get('organization_id')
    manager_name = data.get('manager_name', '')

    if not name:
        return jsonify({'success': False, 'message': '서비스명을 입력하세요.'}), 400

    service = Service.query.get(service_id)
    if not service:
        return jsonify({'success': False, 'message': '서비스를 찾을 수 없습니다.'}), 404

    service.name = name
    # organization_id가 제공되면 업데이트, 없으면 기존 값 유지
    if organization_id:
        service.organization_id = organization_id
    service.manager_name = manager_name
    db.session.commit()

    return jsonify({'success': True, 'message': '서비스가 수정되었습니다.'})

# API: 서비스 삭제
@app.route('/api/service/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    service = Service.query.get(service_id)
    if not service:
        return jsonify({'success': False, 'message': '서비스를 찾을 수 없습니다.'}), 404

    # 해당 서비스의 발송 요청이 있는지 확인
    requests = SendRequest.query.filter_by(service_id=service_id).count()
    if requests > 0:
        return jsonify({'success': False, 'message': f'이 서비스에 {requests}개의 캠페인 신청이 있습니다. 먼저 캠페인을 삭제해주세요.'}), 400

    db.session.delete(service)
    db.session.commit()

    return jsonify({'success': True, 'message': '서비스가 삭제되었습니다.'})

# API: 조직의 서비스 목록 조회
@app.route('/api/services/<int:org_id>')
def get_services(org_id):
    services = Service.query.filter_by(organization_id=org_id).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'manager_name': s.manager_name
    } for s in services])

# API: 모든 서비스 목록 조회
@app.route('/api/services')
def get_all_services():
    services = Service.query.join(Organization).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'organization_name': s.organization.name,
        'manager_name': s.manager_name,
        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(s, 'created_at') and s.created_at else '-'
    } for s in services])

# API: 모든 조직 목록 조회
@app.route('/api/organizations')
def get_all_organizations():
    orgs = Organization.query.all()
    return jsonify([{
        'id': o.id,
        'name': o.name,
        'created_at': o.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(o, 'created_at') and o.created_at else '-'
    } for o in orgs])

# API: 물량 신청
@app.route('/api/request', methods=['POST'])
def create_request():
    data = request.json
    service_id = data.get('service_id')
    send_date = datetime.strptime(data.get('send_date'), '%Y-%m-%d').date()
    channel = data.get('channel', 'naver')
    quantity = data.get('quantity')

    # 해당 월의 조직별 총 물량 확인
    service = Service.query.get(service_id)
    year_month = send_date.strftime('%Y-%m')

    # 프리징 체크
    freeze = MonthlyFreeze.query.filter_by(year_month=year_month).first()
    if freeze and freeze.is_frozen:
        return jsonify({'success': False, 'message': f'{year_month}은(는) 프리징되었습니다. 변경 요청을 이용해주세요.'}), 403

    quota = MonthlyQuota.query.filter_by(
        organization_id=service.organization_id,
        year_month=year_month,
        channel=channel
    ).first()

    if not quota:
        return jsonify({'success': False, 'message': f'해당 월의 {channel} 채널 물량이 설정되지 않았습니다.'}), 400

    # 해당 월의 조직 전체 신청 물량 계산 (채널별)
    month_start = datetime.strptime(year_month + '-01', '%Y-%m-%d').date()
    if send_date.month == 12:
        month_end = datetime.strptime(f'{send_date.year + 1}-01-01', '%Y-%m-%d').date()
    else:
        month_end = datetime.strptime(f'{send_date.year}-{send_date.month + 1:02d}-01', '%Y-%m-%d').date()

    total_requested = db.session.query(func.sum(SendRequest.quantity)).join(Service).filter(
        Service.organization_id == service.organization_id,
        SendRequest.channel == channel,
        SendRequest.send_date >= month_start,
        SendRequest.send_date < month_end
    ).scalar() or 0

    if total_requested + quantity > quota.total_quota:
        remaining = quota.total_quota - total_requested
        return jsonify({
            'success': False,
            'message': f'{channel} 채널 물량을 초과합니다. 남은 물량: {remaining:,}건'
        }), 400

    send_time = data.get('send_time')
    campaign_name = data.get('campaign_name')

    send_request = SendRequest(
        service_id=service_id,
        send_date=send_date,
        send_time=send_time,
        channel=channel,
        campaign_name=campaign_name,
        quantity=quantity
    )
    db.session.add(send_request)
    db.session.commit()

    return jsonify({'success': True, 'message': '물량이 신청되었습니다.'})

# API: 달력용 물량 현황 조회 (조직별, 채널별)
@app.route('/api/calendar/<int:org_id>/<year_month>')
def get_calendar_data(org_id, year_month):
    channel = request.args.get('channel', 'all')  # all, naver, payco, talktalk

    month_start = datetime.strptime(year_month + '-01', '%Y-%m-%d').date()
    year = int(year_month.split('-')[0])
    month = int(year_month.split('-')[1])

    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    query = db.session.query(
        SendRequest.send_date,
        Service.name,
        SendRequest.channel,
        SendRequest.quantity,
        SendRequest.send_time,
        SendRequest.campaign_name
    ).join(Service).filter(
        Service.organization_id == org_id,
        SendRequest.send_date >= month_start,
        SendRequest.send_date < month_end
    )

    if channel != 'all':
        query = query.filter(SendRequest.channel == channel)

    requests = query.all()

    calendar_data = {}
    for req in requests:
        date_str = req.send_date.strftime('%Y-%m-%d')
        if date_str not in calendar_data:
            calendar_data[date_str] = []
        calendar_data[date_str].append({
            'service': req.name,
            'channel': req.channel,
            'quantity': req.quantity,
            'time': req.send_time,
            'campaign_name': req.campaign_name
        })

    # 채널별 물량 정보
    quotas = {}
    if channel == 'all':
        all_quotas = MonthlyQuota.query.filter_by(
            organization_id=org_id,
            year_month=year_month
        ).all()
        for q in all_quotas:
            quotas[q.channel] = q.total_quota
    else:
        quota = MonthlyQuota.query.filter_by(
            organization_id=org_id,
            year_month=year_month,
            channel=channel
        ).first()
        if quota:
            quotas[channel] = quota.total_quota

    total_quota = sum(quotas.values())
    total_requested = sum(req.quantity for req in requests)

    return jsonify({
        'calendar_data': calendar_data,
        'total_quota': total_quota,
        'quotas_by_channel': quotas,
        'total_requested': total_requested,
        'remaining': total_quota - total_requested
    })

# API: 달력용 전체 물량 현황 조회 (모든 조직)
@app.route('/api/calendar/all/<year_month>')
def get_calendar_data_all(year_month):
    channel = request.args.get('channel', 'all')

    month_start = datetime.strptime(year_month + '-01', '%Y-%m-%d').date()
    year = int(year_month.split('-')[0])
    month = int(year_month.split('-')[1])

    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    # 전체 조직의 신청 내역 조회
    query = db.session.query(
        SendRequest.send_date,
        Service.name,
        Organization.name.label('org_name'),
        SendRequest.channel,
        SendRequest.quantity,
        SendRequest.send_time,
        SendRequest.campaign_name
    ).join(Service, SendRequest.service_id == Service.id
    ).join(Organization, Service.organization_id == Organization.id
    ).filter(
        SendRequest.send_date >= month_start,
        SendRequest.send_date < month_end
    )

    if channel != 'all':
        query = query.filter(SendRequest.channel == channel)

    requests = query.all()

    calendar_data = {}
    for req in requests:
        date_str = req.send_date.strftime('%Y-%m-%d')
        if date_str not in calendar_data:
            calendar_data[date_str] = []
        calendar_data[date_str].append({
            'service': f"{req.org_name} - {req.name}",
            'channel': req.channel,
            'quantity': req.quantity,
            'time': req.send_time,
            'campaign_name': req.campaign_name
        })

    # 전체 조직의 물량 정보
    quotas_query = MonthlyQuota.query.filter_by(year_month=year_month)
    if channel != 'all':
        quotas_query = quotas_query.filter_by(channel=channel)

    all_quotas = quotas_query.all()
    total_quota = sum(q.total_quota for q in all_quotas)
    total_requested = sum(req.quantity for req in requests)

    return jsonify({
        'calendar_data': calendar_data,
        'total_quota': total_quota,
        'total_requested': total_requested,
        'remaining': total_quota - total_requested
    })

# API: 달력용 물량 현황 조회 (서비스별)
@app.route('/api/calendar/service/<int:service_id>/<year_month>')
def get_calendar_data_by_service(service_id, year_month):
    month_start = datetime.strptime(year_month + '-01', '%Y-%m-%d').date()
    year = int(year_month.split('-')[0])
    month = int(year_month.split('-')[1])

    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    service = Service.query.get(service_id)
    if not service:
        return jsonify({'error': '서비스를 찾을 수 없습니다.'}), 404

    requests = db.session.query(
        SendRequest.send_date,
        Service.name,
        SendRequest.quantity,
        SendRequest.channel,
        SendRequest.send_time,
        SendRequest.campaign_name
    ).join(Service).filter(
        SendRequest.service_id == service_id,
        SendRequest.send_date >= month_start,
        SendRequest.send_date < month_end
    ).all()

    calendar_data = {}
    for req in requests:
        date_str = req.send_date.strftime('%Y-%m-%d')
        if date_str not in calendar_data:
            calendar_data[date_str] = []
        calendar_data[date_str].append({
            'service': req.name,
            'quantity': req.quantity,
            'channel': req.channel,
            'time': req.send_time,
            'campaign_name': req.campaign_name
        })

    # 해당 서비스의 조직 물량 정보
    quota = MonthlyQuota.query.filter_by(
        organization_id=service.organization_id,
        year_month=year_month
    ).first()

    total_requested = sum(req.quantity for req in requests)

    return jsonify({
        'calendar_data': calendar_data,
        'total_quota': quota.total_quota if quota else 0,
        'total_requested': total_requested,
        'remaining': (quota.total_quota if quota else 0) - total_requested
    })

# API: 서비스별 신청 목록 조회
@app.route('/api/requests/service/<int:service_id>')
def get_requests_by_service(service_id):
    from datetime import datetime, time as dt_time

    # 오늘 날짜 (KST)
    kst_now = datetime.now(KST)
    today = kst_now.date()
    current_time = kst_now.time()

    # 오늘 이후의 캠페인만 조회
    requests = SendRequest.query.filter_by(service_id=service_id).filter(
        SendRequest.send_date >= today
    ).order_by(
        SendRequest.send_date.asc(),
        SendRequest.send_time.asc(),
        SendRequest.created_at.desc()
    ).all()

    # 오늘 날짜인 경우 현재 시간 이후만 필터링
    filtered_requests = []
    for r in requests:
        if r.send_date == today:
            # 오늘 날짜인 경우 시간 체크
            if r.send_time:
                # send_time이 문자열 형태 (HH:MM)
                try:
                    hour, minute = map(int, r.send_time.split(':'))
                    send_time_obj = dt_time(hour, minute)
                    if send_time_obj >= current_time:
                        filtered_requests.append(r)
                except:
                    # 파싱 실패 시 포함
                    filtered_requests.append(r)
            else:
                # 시간 미정인 경우 포함
                filtered_requests.append(r)
        else:
            # 미래 날짜는 모두 포함
            filtered_requests.append(r)

    channel_names = {
        'naver': '네이버앱',
        'payco': '페이앱',
        'talktalk': '톡톡'
    }

    return jsonify([{
        'id': r.id,
        'send_date': r.send_date.strftime('%Y-%m-%d'),
        'send_time': r.send_time or '-',
        'channel': r.channel,
        'channel_name': channel_names.get(r.channel, r.channel),
        'campaign_name': r.campaign_name or '-',
        'quantity': r.quantity,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in filtered_requests])

# API: 조직별 신청 목록 조회
@app.route('/api/requests/org/<int:org_id>')
def get_requests_by_org(org_id):
    requests = db.session.query(
        SendRequest.id,
        SendRequest.send_date,
        SendRequest.send_time,
        SendRequest.channel,
        SendRequest.campaign_name,
        SendRequest.quantity,
        SendRequest.created_at,
        Service.name.label('service_name'),
        Organization.name.label('org_name')
    ).join(Service, SendRequest.service_id == Service.id
    ).join(Organization, Service.organization_id == Organization.id
    ).filter(Organization.id == org_id
    ).order_by(SendRequest.send_date.desc(), SendRequest.created_at.desc()).all()

    channel_names = {
        'naver': '네이버앱',
        'payco': '페이앱',
        'talktalk': '톡톡'
    }

    return jsonify([{
        'id': r.id,
        'send_date': r.send_date.strftime('%Y-%m-%d'),
        'send_time': r.send_time or '-',
        'channel': r.channel,
        'channel_name': channel_names.get(r.channel, r.channel),
        'campaign_name': r.campaign_name or '-',
        'quantity': r.quantity,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        'service_name': r.service_name,
        'org_name': r.org_name
    } for r in requests])

# API: 전체 신청 목록 조회
@app.route('/api/requests/all')
def get_all_requests():
    requests = db.session.query(
        SendRequest.id,
        SendRequest.send_date,
        SendRequest.send_time,
        SendRequest.channel,
        SendRequest.campaign_name,
        SendRequest.quantity,
        SendRequest.created_at,
        Service.name.label('service_name'),
        Organization.name.label('org_name')
    ).join(Service, SendRequest.service_id == Service.id
    ).join(Organization, Service.organization_id == Organization.id
    ).order_by(SendRequest.send_date.desc(), SendRequest.created_at.desc()).all()

    channel_names = {
        'naver': '네이버앱',
        'payco': '페이앱',
        'talktalk': '톡톡'
    }

    return jsonify([{
        'id': r.id,
        'send_date': r.send_date.strftime('%Y-%m-%d'),
        'send_time': r.send_time or '-',
        'channel': r.channel,
        'channel_name': channel_names.get(r.channel, r.channel),
        'campaign_name': r.campaign_name or '-',
        'quantity': r.quantity,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        'service_name': r.service_name,
        'org_name': r.org_name
    } for r in requests])

# API: 신청 삭제
@app.route('/api/request/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    req = SendRequest.query.get(request_id)
    if not req:
        return jsonify({'success': False, 'message': '해당 신청을 찾을 수 없습니다.'}), 404

    # 프리징 체크
    year_month = req.send_date.strftime('%Y-%m')
    freeze = MonthlyFreeze.query.filter_by(year_month=year_month).first()
    if freeze and freeze.is_frozen:
        return jsonify({'success': False, 'message': f'{year_month}은(는) 프리징되었습니다. 변경 요청을 이용해주세요.'}), 403

    db.session.delete(req)
    db.session.commit()

    return jsonify({'success': True, 'message': '신청이 삭제되었습니다.'})

# API: 프리징 상태 조회
@app.route('/api/freeze/<year_month>')
def get_freeze_status(year_month):
    freeze = MonthlyFreeze.query.filter_by(year_month=year_month).first()
    if freeze:
        return jsonify({
            'is_frozen': freeze.is_frozen,
            'frozen_at': freeze.frozen_at.strftime('%Y-%m-%d %H:%M') if freeze.frozen_at else None,
            'frozen_by': freeze.frozen_by
        })
    return jsonify({'is_frozen': False})

# API: 프리징 설정 (관리자)
@app.route('/api/freeze', methods=['POST'])
def set_freeze():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    year_month = data.get('year_month')
    is_frozen = data.get('is_frozen')

    freeze = MonthlyFreeze.query.filter_by(year_month=year_month).first()

    if freeze:
        freeze.is_frozen = is_frozen
        if is_frozen:
            freeze.frozen_at = kst_now()
            freeze.frozen_by = '관리자'
    else:
        freeze = MonthlyFreeze(
            year_month=year_month,
            is_frozen=is_frozen,
            frozen_at=kst_now() if is_frozen else None,
            frozen_by='관리자' if is_frozen else None
        )
        db.session.add(freeze)

    db.session.commit()

    status_text = '프리징' if is_frozen else '프리징 해제'
    return jsonify({'success': True, 'message': f'{year_month}이(가) {status_text}되었습니다.'})

# API: 모든 프리징 목록 조회
@app.route('/api/freezes')
def get_all_freezes():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    freezes = MonthlyFreeze.query.order_by(MonthlyFreeze.year_month.desc()).all()
    return jsonify([{
        'year_month': f.year_month,
        'is_frozen': f.is_frozen,
        'frozen_at': f.frozen_at.strftime('%Y-%m-%d %H:%M') if f.frozen_at else None,
        'frozen_by': f.frozen_by
    } for f in freezes])

# API: 변경 요청 생성
@app.route('/api/change-request', methods=['POST'])
def create_change_request():
    data = request.json

    # send_date로부터 year_month 추출
    year_month = None
    if data.get('send_date'):
        send_date = datetime.strptime(data.get('send_date'), '%Y-%m-%d').date()
        year_month = f"{send_date.year}-{str(send_date.month).zfill(2)}"
    elif data.get('request_type') == 'delete' and data.get('original_request_id'):
        # 삭제 요청인 경우 원본 요청의 날짜에서 추출
        original = SendRequest.query.get(data.get('original_request_id'))
        if original:
            year_month = f"{original.send_date.year}-{str(original.send_date.month).zfill(2)}"

    change_req = ChangeRequest(
        year_month=year_month,
        request_type=data.get('request_type'),
        service_id=data.get('service_id'),
        original_request_id=data.get('original_request_id'),
        send_date=datetime.strptime(data.get('send_date'), '%Y-%m-%d').date() if data.get('send_date') else None,
        send_time=data.get('send_time'),
        channel=data.get('channel'),
        campaign_name=data.get('campaign_name'),
        quantity=data.get('quantity'),
        reason=data.get('reason'),
        requester_name=data.get('requester_name')
    )

    db.session.add(change_req)
    db.session.commit()

    return jsonify({'success': True, 'message': '변경 요청이 등록되었습니다.'})

# API: 변경 요청 목록 조회
@app.route('/api/change-requests')
def get_change_requests():
    status_filter = request.args.get('status')

    query = db.session.query(
        ChangeRequest,
        Service.name.label('service_name'),
        Organization.name.label('org_name')
    ).join(Service, ChangeRequest.service_id == Service.id
    ).join(Organization, Service.organization_id == Organization.id)

    if status_filter:
        query = query.filter(ChangeRequest.status == status_filter)

    change_requests = query.order_by(ChangeRequest.created_at.desc()).all()

    request_type_names = {
        'add': '신규 추가',
        'modify': '수정',
        'delete': '삭제'
    }

    status_names = {
        'pending': '대기중',
        'approved': '승인',
        'rejected': '거부'
    }

    channel_names = {
        'naver': '네이버앱',
        'payco': '페이앱',
        'talktalk': '톡톡'
    }

    return jsonify([{
        'id': cr.id,
        'year_month': cr.year_month,
        'request_type': cr.request_type,
        'request_type_name': request_type_names.get(cr.request_type, cr.request_type),
        'org_name': org_name,
        'service_name': service_name,
        'send_date': cr.send_date.strftime('%Y-%m-%d') if cr.send_date else None,
        'send_time': cr.send_time or '-',
        'channel': cr.channel,
        'channel_name': channel_names.get(cr.channel, cr.channel) if cr.channel else '-',
        'campaign_name': cr.campaign_name or '-',
        'quantity': cr.quantity,
        'reason': cr.reason,
        'requester_name': cr.requester_name,
        'status': cr.status,
        'status_name': status_names.get(cr.status, cr.status),
        'admin_memo': cr.admin_memo,
        'processed_by': cr.processed_by,
        'processed_at': cr.processed_at.strftime('%Y-%m-%d %H:%M') if cr.processed_at else None,
        'created_at': cr.created_at.strftime('%Y-%m-%d %H:%M')
    } for cr, service_name, org_name in change_requests])

# API: 변경 요청 처리 (승인/거부)
@app.route('/api/change-request/<int:request_id>', methods=['PUT'])
def process_change_request(request_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    change_req = ChangeRequest.query.get(request_id)

    if not change_req:
        return jsonify({'success': False, 'message': '변경 요청을 찾을 수 없습니다.'}), 404

    action = data.get('action')  # approve, reject
    admin_memo = data.get('admin_memo', '')

    if action == 'approve':
        # 변경 요청 승인 처리
        if change_req.request_type == 'add':
            # 신규 캠페인 추가
            new_request = SendRequest(
                service_id=change_req.service_id,
                send_date=change_req.send_date,
                send_time=change_req.send_time,
                channel=change_req.channel,
                campaign_name=change_req.campaign_name,
                quantity=change_req.quantity
            )
            db.session.add(new_request)
        elif change_req.request_type == 'modify':
            # 기존 캠페인 수정
            original = SendRequest.query.get(change_req.original_request_id)
            if original:
                if change_req.send_date:
                    original.send_date = change_req.send_date
                if change_req.send_time:
                    original.send_time = change_req.send_time
                if change_req.channel:
                    original.channel = change_req.channel
                if change_req.campaign_name:
                    original.campaign_name = change_req.campaign_name
                if change_req.quantity:
                    original.quantity = change_req.quantity
        elif change_req.request_type == 'delete':
            # 기존 캠페인 삭제
            original = SendRequest.query.get(change_req.original_request_id)
            if original:
                db.session.delete(original)

        change_req.status = 'approved'
        change_req.admin_memo = admin_memo
        change_req.processed_by = '관리자'
        change_req.processed_at = kst_now()

        db.session.commit()
        return jsonify({'success': True, 'message': '변경 요청이 승인되었습니다.'})

    elif action == 'reject':
        change_req.status = 'rejected'
        change_req.admin_memo = admin_memo
        change_req.processed_by = '관리자'
        change_req.processed_at = kst_now()

        db.session.commit()
        return jsonify({'success': True, 'message': '변경 요청이 거부되었습니다.'})

    return jsonify({'success': False, 'message': '잘못된 요청입니다.'}), 400

# 초기 데이터 생성
@app.route('/init')
def init_data():
    db.drop_all()
    db.create_all()

    # 조직 생성
    orgs = {
        'AD사업개발': Organization(name='AD사업개발'),
        '내부제휴서비스': Organization(name='내부제휴서비스'),
        '내자산': Organization(name='내자산'),
        '대출': Organization(name='대출'),
        '마이카': Organization(name='마이카'),
        '마케팅스튜디오': Organization(name='마케팅스튜디오'),
        '보험': Organization(name='보험'),
        '외부제휴서비스': Organization(name='외부제휴서비스'),
        '증권': Organization(name='증권'),
        '카드CPA': Organization(name='카드CPA'),
        '페이앱': Organization(name='페이앱'),
        '현장결제': Organization(name='현장결제'),
    }

    for org in orgs.values():
        db.session.add(org)
    db.session.commit()

    # 서비스 생성
    services = [
        # AD사업개발
        Service(name='프리미엄패키지', organization_id=orgs['AD사업개발'].id, manager_name='박종호'),

        # 내부제휴서비스
        Service(name='사용자마케팅', organization_id=orgs['내부제휴서비스'].id, manager_name='유진'),

        # 내자산
        Service(name='내자산 신규 등록', organization_id=orgs['내자산'].id, manager_name='김정희'),

        # 대출
        Service(name='신용대출비교', organization_id=orgs['대출'].id, manager_name='정채연'),
        Service(name='신용대환대출', organization_id=orgs['대출'].id, manager_name='정채연'),
        Service(name='신용점수', organization_id=orgs['대출'].id, manager_name='서원교'),
        Service(name='신차리스', organization_id=orgs['대출'].id, manager_name='허호필'),
        Service(name='전월세대출비교', organization_id=orgs['대출'].id, manager_name='정채연'),
        Service(name='주택담보대출비교', organization_id=orgs['대출'].id, manager_name='정채연'),
        Service(name='중고차론', organization_id=orgs['대출'].id, manager_name='허호필'),

        # 마이카
        Service(name='내차등록', organization_id=orgs['마이카'].id, manager_name='허호필'),

        # 마케팅스튜디오
        Service(name='마케팅부스팅', organization_id=orgs['마케팅스튜디오'].id, manager_name='오인숙'),
        Service(name='애플', organization_id=orgs['마케팅스튜디오'].id, manager_name='최승민'),
        Service(name='프로모션', organization_id=orgs['마케팅스튜디오'].id, manager_name='최용우'),

        # 보험
        Service(name='내자산 신규 등록(보험)', organization_id=orgs['보험'].id, manager_name='조은수'),
        Service(name='보험가입', organization_id=orgs['보험'].id, manager_name='이은혜'),
        Service(name='자동차보험중개', organization_id=orgs['보험'].id, manager_name='강경필'),
        Service(name='해외여행보험중개', organization_id=orgs['보험'].id, manager_name='강경필'),

        # 외부제휴서비스
        Service(name='외부제휴_서비스', organization_id=orgs['외부제휴서비스'].id, manager_name='임태경'),
        Service(name='외부제휴_쇼핑', organization_id=orgs['외부제휴서비스'].id, manager_name='임태경'),

        # 증권
        Service(name='증권토론', organization_id=orgs['증권'].id, manager_name='정인아'),

        # 카드CPA
        Service(name='KB카드', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='네이버페이 머니카드', organization_id=orgs['카드CPA'].id, manager_name='정민주'),
        Service(name='롯데카드 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='삼성카드 제휴 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='신한카드 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='신한카드 제휴 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='우리카드 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),
        Service(name='현대카드 CPA', organization_id=orgs['카드CPA'].id, manager_name='강창민'),

        # 페이앱
        Service(name='페이앱설치', organization_id=orgs['페이앱'].id, manager_name='이재형'),

        # 현장결제
        Service(name='오프라인 현장결제', organization_id=orgs['현장결제'].id, manager_name='신현확'),
        Service(name='오프라인 해외결제', organization_id=orgs['현장결제'].id, manager_name='김민지'),
    ]

    db.session.add_all(services)
    db.session.commit()

    return jsonify({'success': True, 'message': '초기 데이터가 생성되었습니다.'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
else:
    # Production: Initialize database when imported by gunicorn
    with app.app_context():
        db.create_all()