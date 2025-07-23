from flask import Flask, Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import func
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message as MailMessage
import os
from datetime import datetime
import time
import requests
import cohere
from dotenv import load_dotenv
from flask_migrate import Migrate
import random
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fpdf import FPDF
import matplotlib.pyplot as plt

# === 應用設定 ===
app = Flask(__name__, template_folder='templates', instance_relative_config=True)
CORS(app)
app.secret_key = 'ncku_elearning_secret_key_2024'

# 建立 instance 資料夾（存資料庫）
os.makedirs(app.instance_path, exist_ok=True)

# === 資料庫設定 ===
db_path = os.path.join(app.instance_path, 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# === 郵件設定（請填入你自己的 Gmail）===
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'axe22641370@gmail.com'
app.config['MAIL_PASSWORD'] = 'fmtf pclj klfn gqsg'
mail = Mail(app)


def get_option_text(option_key, ans):
    mapping = {
        "answer_a": ans.answer_a,
        "answer_b": ans.answer_b,
        "answer_c": ans.answer_c,
        "answer_d": ans.answer_d
    }
    return mapping.get(option_key, "[未知選項]")

import matplotlib.pyplot as plt

def generate_score_curve_image(user, results, chart_path):
    scores = [r.score for r in results]
    total_questions = [len(r.answers) for r in results]
    times = [r.total_time for r in results]
    labels = [f"Test {i+1}" for i in range(len(results))]

    plt.figure(figsize=(8, 4))
    plt.plot(labels, scores, marker='o', label="Score")
    plt.ylim(0, max(total_questions) + 1)
    plt.xlabel("Attempt")
    plt.ylabel("Correct Answers")
    plt.title(f"{user.name}'s Quiz Score History")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()


class UnicodePDF(FPDF):
    def __init__(self):
        super().__init__()
        font_dir = os.path.join("app", "fonts", "Noto_Sans_TC", "static")
        self.add_font("Noto", "", os.path.join(font_dir, "NotoSansTC-Regular.ttf"), uni=True)
        self.add_font("Noto", "B", os.path.join(font_dir, "NotoSansTC-Bold.ttf"), uni=True)
        self.set_font("Noto", size=12)

# scheduler定義
def generate_and_send_pdf_report():
    with app.app_context():
        users = User.query.all()

        for user in users:
            results = QuizResult.query.filter_by(user_id=user.id).order_by(QuizResult.timestamp.asc()).all()
            if not results:
                continue

            pdf = UnicodePDF()
            pdf.add_page()
            pdf.set_font("Noto", size=14)
            pdf.cell(0, 10, f"{user.name}'s Quiz Report", ln=True)
            pdf.ln(5)

            # === 分數變化圖 ===
            chart_path = f"app/reports/chart_{user.id}.png"
            generate_score_curve_image(user, results, chart_path)

            img_width = 180
            img_height = img_width * 3 / 4
            img_x = 10
            img_y = pdf.get_y()
            pdf.image(chart_path, x=img_x, y=img_y, w=img_width)
            pdf.ln(img_height + 5)

            if pdf.get_y() > 250:
                pdf.add_page()

            # === 寫入每次測驗詳解 ===
            for i, result in enumerate(results):
                pdf.set_font("Noto", style='', size=12)
                pdf.cell(0, 10, txt=f"Test {i + 1}: {result.score}/{len(result.answers)} correct, time {result.total_time:.1f} sec", ln=True)
                pdf.set_font("Noto", size=11)
                pdf.ln(2)

                for idx, ans in enumerate(result.answers, start=1):
                    mark = "正確" if ans.is_correct else "錯誤"

                    pdf.set_font("Noto", style='B', size=12)
                    pdf.set_x(10)
                    pdf.multi_cell(190, 8, text=f"{mark} - 題目 {idx}：{ans.question_text}")

                    pdf.set_font("Noto", size=11)
                    pdf.set_x(10)
                    pdf.multi_cell(190, 8, text=f"你的答案：{get_option_text(ans.selected_option, ans)}")

                    pdf.set_x(10)
                    pdf.multi_cell(190, 8, text=f"正確答案：{get_option_text(ans.correct_option, ans)}")

                    if ans.explanation:
                        pdf.set_x(10)
                        pdf.multi_cell(190, 8, text=f"解析：{ans.explanation.strip()}")

                    pdf.ln(5)
                    if pdf.get_y() > 260:
                        pdf.add_page()

                # 如果頁面快滿，換頁
                if pdf.get_y() > 260:
                    pdf.add_page()

                pdf.ln(5)

            # 儲存 PDF
            output_dir = os.path.join("app", "reports")
            os.makedirs(output_dir, exist_ok=True)
            filename = f"report_{user.id}.pdf"
            filepath = os.path.join(output_dir, filename)
            pdf.output(filepath)

            # 寄送 Email
            msg = MailMessage(
                subject="Your Quiz Report",
                sender=app.config['MAIL_USERNAME'],
                recipients=[user.email]
            )
            msg.body = f"Hello {user.name}, please find your quiz performance report attached. It includes your score trend and detailed answers."
            with open(filepath, "rb") as f:
                msg.attach(filename, "application/pdf", f.read())

            try:
                mail.send(msg)
                print(f"[Success] Report sent to {user.email}")
            except Exception as e:
                print(f"[Error] Failed to send to {user.email}: {e}")

# 初始化scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=generate_and_send_pdf_report,
    trigger=CronTrigger(hour=23, minute=59),
    id='daily_report',
    replace_existing=True
)
scheduler.start()

# === Google Custom Search API 設定 ===
GOOGLE_API_KEY = "AIzaSyAtONnF76x8Jz5VP-Fs8gUt35DV9-gXSvc"
GOOGLE_CX = "b352df7b1c939469b"

def google_search(query, num_results=3):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": num_results,
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        results = []

        for item in data.get("items", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet")
            })
        return results
    except Exception as e:
        print("Google 搜尋錯誤：", str(e))
        return []

# 資料模型
class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    number = db.Column(db.String(20))
    msg = db.Column(db.Text)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10))

class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cover_image = db.Column(db.String(255), nullable=True)  # 儲存圖片檔名
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('User', backref='courses')


class Video(db.Model):
    __tablename__ = 'video'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)  # 影片所屬課程
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    youtube_id = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', backref=db.backref('videos', lazy=True))


# 紀錄收藏清單
class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

    user = db.relationship('User', backref='bookmarks')
    course = db.relationship('Course', backref='bookmarked_by')

class VideoLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_video_like'),)

    user = db.relationship('User', backref='liked_videos')
    video = db.relationship('Video', backref='liked_by_users')

class QuizResult(db.Model):
    __tablename__ = 'quiz_result'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer)
    total_time = db.Column(db.Float)
    answers = db.relationship('QuizAnswer', backref='result')


class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answer'
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('quiz_result.id'))  
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    question_text = db.Column(db.Text)
    answer_a = db.Column(db.String(255))
    answer_b = db.Column(db.String(255))
    answer_c = db.Column(db.String(255))
    answer_d = db.Column(db.String(255))
    selected_option = db.Column(db.String(20))   # e.g. 'answer_a'
    correct_option = db.Column(db.String(20))    # e.g. 'answer_b'
    is_correct = db.Column(db.Boolean, nullable=False)
    explanation = db.Column(db.Text)

# 建立資料表
with app.app_context():
    db.create_all()

# === 路由 ===
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/progress")
def progress():
    results = session.get('quiz_results', [])
    score = session.get('score', 0)
    total = session.get('total', len(results))
    return render_template("progress.html", results=results, score=score, total=total)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/courses')
def courses():
    course_data = []

    courses = Course.query.all()
    for course in courses:
        # 查出老師資訊
        teacher = User.query.get(course.teacher_id)
        teacher_name = teacher.name if teacher else "未知老師"

        # 查出該課程的影片數量
        video_count = Video.query.filter_by(course_id=course.id).count()

        # 組合資料進 dict
        course_data.append({
            'id': course.id,
            'title': course.title,
            'cover_image': course.cover_image,
            'created_at': course.created_at,
            'teacher_name': teacher_name,
            'video_count': video_count
        })

    return render_template('courses.html', courses=course_data)




@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        image = request.files.get('cover')
        teacher_id = session.get('user_id')  # 登入後應有 user_id

        if not all([title, description, image, teacher_id]):
            flash("請填寫完整資料")
            return redirect(url_for('add_course'))

        filename = secure_filename(image.filename)
        image.save(os.path.join('static/course_images', filename))

        new_course = Course(
            title=title,
            description=description,
            cover_image=filename,
            teacher_id=teacher_id
        )
        db.session.add(new_course)
        db.session.commit()

        session['last_course'] = {
            'id': new_course.id,
            'title': title,
            'cover': filename
        }

        flash("課程已成功新增")
        return redirect(url_for('courses'))

    return render_template('add_course.html')  # GET 時顯示表單


@app.route('/upload_youtube', methods=['POST'])
def upload_youtube():
    try:
        data = request.get_json()

        video = Video(
            title=data['title'],
            description=data['description'],
            youtube_id=data['youtube_id'],
            course_id=data['course_id']
        )
        db.session.add(video)
        db.session.commit()

        return jsonify({'message': '已儲存影片資料'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/game1', endpoint='game1')
def blockly():
    return render_template("game1.html")

@app.route('/blockly')
def blockly():
    return render_template('blockly.html')


@app.route('/teachers')
def teachers():
    teacher_users = User.query.filter_by(role='teacher').all()

    for teacher in teacher_users:
        courses = Course.query.filter_by(teacher_id=teacher.id).all()
        course_ids = [course.id for course in courses]

        # 所有該老師開的影片
        videos = []
        if course_ids:
            videos = Video.query.filter(Video.course_id.in_(course_ids)).all()
        video_ids = [v.id for v in videos]

        # 撈總播放清單（=課程數）、影片數、被按讚數
        teacher.total_playlists = len(courses)
        teacher.total_videos = len(videos)

        if video_ids:
            teacher.total_likes = db.session.query(func.count(VideoLike.id)).filter(VideoLike.video_id.in_(video_ids)).scalar()
        else:
            teacher.total_likes = 0

    return render_template('teachers.html', teachers=teacher_users)


@app.route('/playlist/<int:course_id>')
def playlist(course_id):
    course = Course.query.get_or_404(course_id)
    videos = Video.query.filter_by(course_id=course_id).all()

    # 預設為未收藏播放清單
    is_bookmarked = False
    liked_video_ids = []

    if 'user_id' in session:
        user_id = session['user_id']
        is_bookmarked = Bookmark.query.filter_by(user_id=user_id, course_id=course_id).first() is not None

        # 撈出使用者喜歡的影片 ID 列表
        liked_video_ids = db.session.query(VideoLike.video_id).filter_by(user_id=user_id).all()
        liked_video_ids = [vid[0] for vid in liked_video_ids]  # 轉成單純的 ID 清單

    return render_template(
        'playlist.html',
        course=course,
        videos=videos,
        is_bookmarked=is_bookmarked,
        liked_video_ids=liked_video_ids  # 傳給前端
    )




@app.route('/teacher/<int:teacher_id>', endpoint='teacher_profile')
def show_teacher_profile(teacher_id):
    # 取得老師資料
    return render_template('teacher_profile.html', teacher_id=teacher_id)



@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == "POST":
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        number = request.form.get('number', '').strip()
        msg = request.form.get('msg', '').strip()

        if not all([name, email, number, msg]):
            flash("請填寫所有欄位", "danger")
            return redirect(url_for("contact"))

        # 先建立 email 訊息
        mail_msg = MailMessage(
            subject=f"聯絡表單來自 {name}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['MAIL_USERNAME']],
            body=f"""姓名：{name}
                Email: {email}
                電話: {number}

                訊息內容: {msg}"""
        )

        try:
            mail.send(mail_msg)

            # 寄信成功才儲存到資料庫
            new_msg = Message(name=name, email=email, number=number, msg=msg)
            db.session.add(new_msg)
            db.session.commit()

            flash("訊息已成功寄出並記錄到資料庫。", "success")
        except Exception as e:
            print("寄信失敗：", e)
            flash("寄信失敗，資料未儲存。", "danger")

        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route('/toggle_video_like', methods=['POST'])
def toggle_video_like():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '請先登入'}), 401

    data = request.get_json()
    video_id = data.get('video_id')

    if not video_id:
        return jsonify({'success': False, 'message': '缺少 video_id'}), 400

    like = VideoLike.query.filter_by(user_id=session['user_id'], video_id=video_id).first()
    if like:
        db.session.delete(like)
    else:
        db.session.add(VideoLike(user_id=session['user_id'], video_id=video_id))

    db.session.commit()
    return jsonify({'success': True})

@app.route('/toggle_bookmark/<int:course_id>', methods=['POST'])
def toggle_bookmark(course_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    bookmark = Bookmark.query.filter_by(user_id=session['user_id'], course_id=course_id).first()
    if bookmark:
        db.session.delete(bookmark)
    else:
        new = Bookmark(user_id=session['user_id'], course_id=course_id)
        db.session.add(new)

    db.session.commit()
    return redirect(url_for('playlist', course_id=course_id))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['pass']

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash("登入成功!")
            return redirect(url_for('home'))
        else:
            flash("帳號或密碼錯誤")
            return redirect(url_for('login'))

    return render_template("login.html")

@app.route('/add_review', methods=['POST'])
def add_review():
    name = request.form.get('name')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    return redirect(url_for('about'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # 撈出該使用者喜歡的影片數量
    like_count = db.session.query(VideoLike).filter_by(user_id=user_id).count()
    # 撈出收藏的播放清單數量（如果還沒做也可以先設 0）
    bookmark_count = db.session.query(Bookmark).filter_by(user_id=user_id).count()
    # 答題記錄
    quiz_count = QuizResult.query.filter_by(user_id=user_id).count()

    return render_template('profile.html',
                           bookmark_count=bookmark_count,
                           like_count=like_count,
                           quiz_count=quiz_count)


@app.route('/quiz/history')
def quiz_history():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    results = QuizResult.query.filter_by(user_id=user_id).order_by(QuizResult.timestamp.asc()).all()

    # 預先處理資料（x軸 labels、y軸 data）
    labels = [r.timestamp.strftime("%m/%d %H:%M") for r in results if r.timestamp]
    scores = [r.score for r in results if r.score is not None]

    return render_template('quiz_history.html', results=results, labels=labels, scores=scores)

@app.route('/quiz/retry_wrong')
def retry_wrong():
    user_id = session.get('user_id')
    wrong_answers = db.session.execute(
        db.select(QuizAnswer).where(
            QuizAnswer.user_id == user_id,
            QuizAnswer.selected_option != QuizAnswer.correct_option
        )
    ).scalars().all()
    return render_template('retry_wrong.html', wrong_answers=wrong_answers)


@app.route('/quiz_detail/<int:result_id>')
def quiz_detail(result_id):
    result = QuizResult.query.get_or_404(result_id)
    answers = QuizAnswer.query.filter_by(result_id=result.id).all()
    return render_template('quiz_detail.html', result=result, answers=answers)

@app.route('/update')
def update_profile():
    return render_template("update.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('pass')
        confirm = request.form.get('c_pass')
        role = request.form.get('role')

        if password != confirm:
            flash("密碼不一致，請重新輸入")
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("此Email已被註冊")
            return redirect(url_for('register'))

        new_user = User(name=name, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("註冊成功，請登入")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("你已成功登出", "message")
    return redirect(url_for('home'))

# 題目測驗1
quiz_bp = Blueprint('quiz', __name__, url_prefix='/quiz')

API_KEY = 'M2xTKdRDqMUibGBIC6pLZQrfybwAEcgvHzHIQKpD' 

@app.route('/quiz/start')
def quiz_start():
    # 呼叫 quizapi.io
    response = requests.get(
        'https://quizapi.io/api/v1/questions',
        params={
            'apiKey': API_KEY,
            'limit': 5,
            'category': 'Code',         # 你也可以改成 'Code', 'DevOps', 'SQL', 等
            'difficulty': 'Easy'
        }
    )

    if response.status_code != 200:
        return f"無法取得題目，API 回應錯誤：{response.status_code}"

    api_questions = response.json()

    # 整理題目結構以渲染到前端
    questions = []
    for q in api_questions:
        question_text = q['question']
        options = []
        for key, value in q['answers'].items():
            if value:  # 忽略為 null 的選項
                options.append((key, value))

        correct_answer = [k for k, v in q['correct_answers'].items() if v == "true"][0]  # 單選題

        questions.append({
            'id': q['id'],
            'question': question_text,
            'options': options,
            'correct': correct_answer  # 僅用於後續對答案，不渲染給前端
        })

    # 存在 session 中（僅作答後才使用）
    session['current_quiz'] = questions
    session['quiz_start_time'] = time.time()

    return render_template('quiz.html', questions=questions)

# 程式碼測驗
@app.route("/quiz_submit", methods=["POST"])
def quiz_submit():
    questions = session.get("current_quiz", [])
    start_time = session.get("quiz_start_time", time.time())
    end_time = time.time()
    elapsed_time = round(end_time - start_time)

    results = []
    score = 0

    # 新增 QuizResult
    quiz_result = QuizResult(
        user_id=session.get('user_id'),
        score=0,
        total_time=elapsed_time
    )
    db.session.add(quiz_result)
    db.session.flush()  # 確保 quiz_result.id 可用

    for q in questions:
        user_answer = request.form.get(f"question_{q['id']}")
        correct_key = q['correct'].replace('_correct', '')  # 例：answer_b
        is_correct = user_answer == correct_key
        explanation = get_explanation(q['question'], q['options'], q['correct'])


        options_dict = dict(q['options'])
        if is_correct:
            score += 1

        # 儲存每題答題紀錄
        quiz_answer = QuizAnswer(
            result_id=quiz_result.id,
            user_id=session.get("user_id"),
            question_text=q['question'],
            answer_a=options_dict.get('answer_a'),
            answer_b=options_dict.get('answer_b'),
            answer_c=options_dict.get('answer_c'),
            answer_d=options_dict.get('answer_d'),
            selected_option=user_answer,           # 例：answer_b
            correct_option=correct_key,            # 例：answer_b
            is_correct=is_correct,
            explanation=explanation
        )
        db.session.add(quiz_answer)

        # 建立題目回饋內容（含選項對應）
        results.append({
            "id": q['id'],
            "question": q['question'],
            "options": {
                'a': options_dict.get('answer_a'),
                'b': options_dict.get('answer_b'),
                'c': options_dict.get('answer_c'),
                'd': options_dict.get('answer_d')
            },
            "correct": correct_key,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "explanation": explanation,
            "related_articles": google_search(f"{q['question']} {explanation[:50]}")
        })

    # 更新總分數
    quiz_result.score = score
    db.session.commit()

    total = len(questions)

    return render_template("progress.html",
                           total=total,
                           score=score,
                           elapsed_time=elapsed_time,
                           results=results)


COHERE_API_KEY = 'l4Xk0Um93UcmReZ0PtSMFUomckb1gqthZBxm35UF'
co = cohere.Client(COHERE_API_KEY)

COHERE_ENDPOINT = "https://api.cohere.ai/v1/chat"

def get_explanation(question, options, correct_key):
    option_texts = "\n".join([f"{key}. {val}" for key, val in options])
    
    correct_text = next((val for key, val in options if key == correct_key), None)
    if correct_text is None and options:
        correct_text = options[0][1]
    elif correct_text is None:
        correct_text = "[未知正確答案]"

    prompt = f"""題目：{question}
選項：
{option_texts}
正確答案：{correct_key}. {correct_text}
請針對此題目與正確答案進行詳細解析，讓學生容易理解。
"""

    headers = {
        "Authorization": f"Bearer {COHERE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": prompt,
        "model": "command-r-plus",  # 避免錯用不支援的 model
    }

    try:
        response = requests.post(COHERE_ENDPOINT, json=payload, headers=headers)
        data = response.json()
        return data.get("text", "[解析產生失敗]")
    except Exception as e:
        return f"[無法生成解析：{str(e)}]"
    

# 題庫
code_questions = [
    {
        "id": 1,
        "title": "平方和",
        "description": "請輸入一個正整數 n，輸出從 1 到 n 所有整數的平方和。",
        "sample_input": "5",
        "sample_output": "55",
        "default_code": """#include <iostream>
using namespace std;

int main() {
    return 0;
}"""
    },
    {
        "id": 2,
        "title": "判斷質數",
        "description": "輸入一個整數 n，判斷它是否為質數，是的話輸出 Yes，否則輸出 No。",
        "sample_input": "7",
        "sample_output": "Yes",
        "default_code": """#include <iostream>
using namespace std;

int main() {
    return 0;
}"""
    },
    {
        "id": 3,
        "title": "費氏數列",
        "description": "請輸入一個整數 n，輸出第 n 項費波那契數列（第 1 項為 1，第 2 項為 1）。",
        "sample_input": "6",
        "sample_output": "8",
        "default_code": """#include <iostream>
using namespace std;

int main() {
    return 0;
}"""
    }
]

# 程式測驗
JUDGE0_API = "https://judge0-ce.p.rapidapi.com/submissions?base64_encoded=false&wait=true"
LANGUAGE_ID_CPP = 54

HEADERS = {
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
    "X-RapidAPI-Key": "eb6457db9fmsh51c6241a9311c9fp152214jsne0181fb156a9"
}


@app.route("/code_submit", methods=["POST"])
def submit_code():
    source_code = request.form.get("source_code")
    stdin = request.form.get("stdin")
    question_id = int(request.form.get("question_id"))
    question = next((q for q in code_questions if q["id"] == question_id), None)

    if not question:
        return "題目不存在"

    # 提交至 Judge0 API
    data = {
        "source_code": source_code,
        "language_id": LANGUAGE_ID_CPP,
        "stdin": stdin
    }

    response = requests.post(JUDGE0_API, headers=HEADERS, json=data)

    if response.status_code not in (200, 201):
        return f"Judge0 API 錯誤：{response.status_code}"

    result = response.json()

    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    compile_output = (result.get("compile_output") or "").strip()
    status = result.get("status", {}).get("description", "未知狀態")

    # 判斷正確性
    expected_output = question["sample_output"].strip()
    is_correct = (stdout == expected_output)
    ai_suggestion = None

    # 若錯誤，自動用 Cohere 生成解釋
    if not is_correct:
        prompt = f"""
我想請你幫我修正這段 C++ 程式碼，使它能正確輸出以下描述的功能：

題目：{question['title']}
說明：{question['description']}
範例輸入：{question['sample_input']}
範例輸出：{question['sample_output']}

學生的錯誤程式碼如下：
{source_code}

請你提供正確的 C++ 程式碼，並且簡短解釋修正的重點。
"""

        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "message": prompt,
            "model": "command-r-plus",
            "temperature": 0.5,
            "max_tokens": 300
        }

        try:
            cohere_response = requests.post(COHERE_ENDPOINT, json=payload, headers=headers)
            data = cohere_response.json()
            ai_suggestion = data.get("text", "[解析產生失敗]")
        except Exception as e:
            ai_suggestion = f"[無法生成解析：{str(e)}]"

    return render_template("code_result.html",
                           stdout=stdout,
                           stderr=stderr,
                           compile_output=compile_output,
                           status=status,
                           is_correct=is_correct,
                           question=question,
                           source_code=source_code,
                           stdin=stdin,
                           ai_suggestion=ai_suggestion)

@app.route("/code_quiz")
def code_quiz():
    question = random.choice(code_questions)
    return render_template("code_quiz.html", question=question)

@app.route('/ai-rewrite', methods=['POST'])
def ai_rewrite():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'error': '缺少 prompt'}), 400

        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "message": f"""你現在是一位程式老師，對象是國小的小朋友。
請用簡單、清楚、口語化的方式，解釋以下動作是什麼意思。

以下是學生組合的程式積木動作：
{prompt}

回覆請簡短。
""",
            "model": "command-r-plus",
            "temperature": 0.7,
            "max_tokens": 200
        }

        response = requests.post(COHERE_ENDPOINT, json=payload, headers=headers)
        if response.status_code != 200:
            return jsonify({'error': f'API 回應錯誤: {response.status_code}', 'body': response.text}), 500

        data = response.json()
        rewritten_text = data.get("text", "[未取得回覆]")
        return jsonify({'rewrittenText': rewritten_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # 啟動排程
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=generate_and_send_pdf_report,
        trigger=CronTrigger(hour=17, minute=58),
        id='daily_report',
        replace_existing=True
    )
    scheduler.start()

    app.run(debug=True)