from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///noti_plan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'noti_plan_secret_key_2848'
db = SQLAlchemy(app)

ADMIN_PASSWORD = '2848'

# 모델 정의
class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    services = db.relationship('Service', backref='organization', lazy=True)
    quotas = db.relationship('MonthlyQuota', backref='organization', lazy=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    manager_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    requests = db.relationship('SendRequest', backref='service', lazy=True)

class MonthlyQuota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    channel = db.Column(db.String(20), nullable=False, default='naver')  # naver, payco, talktalk
    total_quota = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
        SendRequest.quantity
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
            'quantity': req.quantity
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
        SendRequest.quantity
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
            'quantity': req.quantity
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
        SendRequest.quantity
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
            'quantity': req.quantity
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
@app.route('/api/requests/<int:service_id>')
def get_requests_by_service(service_id):
    requests = SendRequest.query.filter_by(service_id=service_id).order_by(SendRequest.send_date.desc(), SendRequest.created_at.desc()).all()

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
    } for r in requests])

# API: 신청 삭제
@app.route('/api/request/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    req = SendRequest.query.get(request_id)
    if not req:
        return jsonify({'success': False, 'message': '해당 신청을 찾을 수 없습니다.'}), 404

    db.session.delete(req)
    db.session.commit()

    return jsonify({'success': True, 'message': '신청이 삭제되었습니다.'})

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