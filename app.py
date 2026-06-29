from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import boto3
from botocore.client import Config

R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')
R2_PUBLIC_URL = os.getenv('R2_PUBLIC_URL')

s3 = boto3.client(
    's3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)


load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY')
ADMIN_SIFRE = os.getenv('ADMIN_SIFRE')

UPLOAD_FOLDER = 'static/img/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


db = SQLAlchemy(app)

# ===== MODELLER =====
AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
    5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
    9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}
def gorsel_yukle(dosya):
    if dosya and dosya.filename != '':
        ext = dosya.filename.rsplit('.', 1)[-1].lower()
        if ext in ALLOWED_EXTENSIONS:
            filename = secure_filename(dosya.filename)
            s3.upload_fileobj(
                dosya,
                R2_BUCKET_NAME,
                filename,
                ExtraArgs={'ContentType': dosya.content_type}
            )
            return filename
    return None

def gorsel_url(filename):
    if filename:
        return f"{R2_PUBLIC_URL}/{filename}"
    
    return None
app.jinja_env.globals['gorsel_url'] = gorsel_url

def turkce_tarih(dt):
    return f"{dt.day} {AYLAR[dt.month]} {dt.year}"

class Yazi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(200), nullable=False)
    icerik = db.Column(db.Text, nullable=False)
    kategori = db.Column(db.String(50), default='Blog')
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    ozet = db.Column(db.String(300))
    gorsel = db.Column(db.String(200))
    yorumlar = db.relationship('Yorum', backref='yazi', lazy=True)

    def __repr__(self):
        return f'<Yazi {self.baslik}>'

class Tarif(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(200), nullable=False)
    malzemeler = db.Column(db.Text, nullable=False)
    yapilis = db.Column(db.Text, nullable=False)
    sure = db.Column(db.String(50))
    zorluk = db.Column(db.String(50))
    gorsel = db.Column(db.String(200))
    tarih = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Tarif {self.baslik}>'

class Yorum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    icerik = db.Column(db.Text, nullable=False)
    yazar = db.Column(db.String(100), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    yazi_id = db.Column(db.Integer, db.ForeignKey('yazi.id'), nullable=False)
    begeni_sayisi = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Yorum {self.id}>'

# ===== ROTALAR =====

@app.route("/")
def anasayfa():
    son_yazilar = Yazi.query.order_by(Yazi.tarih.desc()).limit(3).all()
    son_tarifler = Tarif.query.order_by(Tarif.tarih.desc()).limit(3).all()
    return render_template("index.html", yazilar=son_yazilar, tarifler=son_tarifler)

@app.route("/blog")
def blog():
    yazilar = Yazi.query.order_by(Yazi.tarih.desc()).all()
    return render_template("blog.html", yazilar=yazilar)

@app.route("/blog/<int:yazi_id>")
def yazi_detay(yazi_id):
    yazi = Yazi.query.get_or_404(yazi_id)
    yorumlar = Yorum.query.filter_by(yazi_id=yazi_id).order_by(Yorum.tarih.asc()).all()
    return render_template("yazi_detay.html", yazi=yazi, yorumlar=yorumlar)

@app.route("/tarifler")
def tarifler():
    tarifler = Tarif.query.order_by(Tarif.tarih.desc()).all()
    return render_template("tarifler.html", tarifler=tarifler)

@app.route("/hakkimda")
def hakkimda():
    return render_template("hakkimda.html")

@app.route("/blog/<int:yazi_id>/yorum", methods=['POST'])
def yorum_ekle(yazi_id):
    yazi = Yazi.query.get_or_404(yazi_id)
    yorum = Yorum(
        icerik=request.form['icerik'],
        yazar=request.form['yazar'],
        yazi_id=yazi_id
    )
    db.session.add(yorum)
    db.session.commit()
    return redirect(f'/blog/{yazi_id}')

@app.route("/ara")
def ara():
    sorgu = request.args.get('q', '')
    if sorgu:
        yazilar = Yazi.query.filter(
            Yazi.baslik.contains(sorgu) | Yazi.icerik.contains(sorgu)
        ).all()
        tarifler = Tarif.query.filter(
            Tarif.baslik.contains(sorgu) | Tarif.yapilis.contains(sorgu)
        ).all()
    else:
        yazilar = []
        tarifler = []
    return render_template("ara.html", yazilar=yazilar, tarifler=tarifler, sorgu=sorgu)

# ===== ADMİN/VERİTABANI OLUŞTUR =====
@app.route("/admin")
def admin():
    if not session.get('admin'):
        return redirect('/admin/giris')
    yazilar = Yazi.query.order_by(Yazi.tarih.desc()).all()
    tarifler = Tarif.query.order_by(Tarif.tarih.desc()).all()
    return render_template("admin/panel.html", yazilar=yazilar, tarifler=tarifler)

@app.route("/admin/giris", methods=['GET', 'POST'])
def admin_giris():
    if request.method == 'POST':
        if request.form.get('sifre') == ADMIN_SIFRE:
            session['admin'] = True
            return redirect('/admin')
        return render_template("admin/giris.html", hata="Şifre yanlış!")
    return render_template("admin/giris.html")

@app.route("/admin/cikis")
def admin_cikis():
    session.pop('admin', None)
    return redirect('/')

@app.route("/admin/yazi/ekle", methods=['GET', 'POST'])
def yazi_ekle():
    if not session.get('admin'):
        return redirect('/admin/giris')
    if request.method == 'POST':
        gorsel_adi = gorsel_yukle(request.files.get('gorsel'))
        yazi = Yazi(
            baslik=request.form['baslik'],
            icerik=request.form['icerik'],
            ozet=request.form['ozet'],
            kategori=request.form['kategori'],
            gorsel=gorsel_adi
        )
        db.session.add(yazi)
        db.session.commit()
        return redirect('/admin')
    return render_template("admin/yazi_ekle.html")

@app.route("/admin/tarif/ekle", methods=['GET', 'POST'])
def tarif_ekle():
    if not session.get('admin'):
        return redirect('/admin/giris')
    if request.method == 'POST':
        gorsel_adi = gorsel_yukle(request.files.get('gorsel'))
        tarif = Tarif(
            baslik=request.form['baslik'],
            malzemeler=request.form['malzemeler'],
            yapilis=request.form['yapilis'],
            sure=request.form['sure'],
            zorluk=request.form['zorluk'],
            gorsel=gorsel_adi
        )
        db.session.add(tarif)
        db.session.commit()
        return redirect('/admin')
    return render_template("admin/tarif_ekle.html")
@app.route("/admin/yazi/duzenle/<int:yazi_id>", methods=['GET', 'POST'])
def yazi_duzenle(yazi_id):
    if not session.get('admin'):
        return redirect('/admin/giris')
    yazi = Yazi.query.get_or_404(yazi_id)
    if request.method == 'POST':
        yazi.baslik = request.form['baslik']
        yazi.icerik = request.form['icerik']
        yazi.ozet = request.form['ozet']
        yazi.kategori = request.form['kategori']
        gorsel_adi = gorsel_yukle(request.files.get('gorsel'))
        if gorsel_adi:
            yazi.gorsel = gorsel_adi
        db.session.commit()
        return redirect('/admin')
    return render_template("admin/yazi_duzenle.html", yazi=yazi)

@app.route("/admin/yazi/sil/<int:yazi_id>")
def yazi_sil(yazi_id):
    if not session.get('admin'):
        return redirect('/admin/giris')
    yazi = Yazi.query.get_or_404(yazi_id)
    db.session.delete(yazi)
    db.session.commit()
    return redirect('/admin')

@app.route("/admin/tarif/duzenle/<int:tarif_id>", methods=['GET', 'POST'])
def tarif_duzenle(tarif_id):
    if not session.get('admin'):
        return redirect('/admin/giris')
    tarif = Tarif.query.get_or_404(tarif_id)
    if request.method == 'POST':
        tarif.baslik = request.form['baslik']
        tarif.malzemeler = request.form['malzemeler']
        tarif.yapilis = request.form['yapilis']
        tarif.sure = request.form['sure']
        tarif.zorluk = request.form['zorluk']
        gorsel_adi = gorsel_yukle(request.files.get('gorsel'))
        if gorsel_adi:
            tarif.gorsel = gorsel_adi
        db.session.commit()
        return redirect('/admin')
    return render_template("admin/tarif_duzenle.html", tarif=tarif)

@app.route("/admin/tarif/sil/<int:tarif_id>")
def tarif_sil(tarif_id):
    if not session.get('admin'):
        return redirect('/admin/giris')
    tarif = Tarif.query.get_or_404(tarif_id)
    db.session.delete(tarif)
    db.session.commit()
    return redirect('/admin')
@app.template_filter('turkce_tarih')
def turkce_tarih_filter(dt):
    return turkce_tarih(dt)

@app.route("/admin/yorum/sil/<int:yorum_id>")
def yorum_sil(yorum_id):
    if not session.get('admin'):
        return redirect('/admin/giris')
    yorum = Yorum.query.get_or_404(yorum_id)
    yazi_id = yorum.yazi_id
    db.session.delete(yorum)
    db.session.commit()
    return redirect(f'/blog/{yazi_id}')

@app.route("/yorum/<int:yorum_id>/begen", methods=['POST'])
def yorum_begen(yorum_id):
    yorum = Yorum.query.get_or_404(yorum_id)
    begenilenler = session.get('begenilen_yorumlar', [])
    if yorum_id not in begenilenler:
        yorum.begeni_sayisi = (yorum.begeni_sayisi or 0) + 1
        db.session.commit()
        begenilenler.append(yorum_id)
        session['begenilen_yorumlar'] = begenilenler
    return redirect(request.referrer or f'/blog/{yorum.yazi_id}')

@app.route("/tarifler/<int:tarif_id>")
def tarif_detay(tarif_id):
    tarif = Tarif.query.get_or_404(tarif_id)
    return render_template("tarif_detay.html", tarif=tarif)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)