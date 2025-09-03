from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pymysql
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'tajni_kljuc'
UPLOAD_FOLDER = 'static/profilne_slike'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    return pymysql.connect(
        host='localhost', user='root', password='1212',
        database='studentski_popusti_db',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM studentski_popusti")
    popusti = cur.fetchall()
    jmbag = session.get('jmbag')
    poslovi = []
    if jmbag:
        cur.execute("SELECT smjer FROM korisnici WHERE jmbag=%s", (jmbag,))
        korisnik = cur.fetchone()
        if korisnik:
            cur.execute("SELECT * FROM poslovi WHERE smjer=%s", (korisnik['smjer'],))
            poslovi = cur.fetchall()
    conn.close()
    return render_template("home.html", popusti=popusti, poslovi=poslovi)

@app.route("/reg", methods=["GET", "POST"])
def registracija():
    if request.method == "POST":
        ime, prezime, jmbag = request.form["ime"], request.form["prezime"], request.form["jmbag"]
        fakultet, smjer = request.form["fakultet"], request.form["smjer"]
        slika = request.files["slika"]
        filename = None
        if slika and slika.filename:
            filename = secure_filename(slika.filename)
            slika.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn = get_db_connection()
        cur = conn.cursor()
         
        cur.execute("SELECT id FROM korisnici WHERE jmbag=%s", (jmbag,))
        postoji = cur.fetchone()

        if postoji:
            conn.close()
            session['jmbag'] = jmbag
            return redirect(url_for("profil"))  
        
        cur.execute("""
            INSERT INTO korisnici (ime, prezime, jmbag, fakultet, smjer, slika_profila)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (ime, prezime, jmbag, fakultet, smjer, filename))
        conn.commit()
        conn.close()
        session['jmbag'] = jmbag
        return redirect(url_for("profil"))
    return render_template("registracija.html")

@app.route("/profil", methods=["GET", "POST"])
def profil():
    jmbag = session.get('jmbag')
    if not jmbag:
        return redirect(url_for("registracija"))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM korisnici WHERE jmbag=%s", (jmbag,))
    korisnik = cur.fetchone()
    if request.method == "POST":
        poruka = request.form["poruka"]
        cur.execute("""
            INSERT INTO poruke (jmbag_posiljatelja, fakultet, sadrzaj)
            VALUES (%s,%s,%s)
        """, (jmbag, korisnik['fakultet'], poruka))
        conn.commit()
    cur.execute("SELECT * FROM poruke WHERE fakultet=%s ORDER BY vrijeme DESC", (korisnik['fakultet'],))
    poruke = cur.fetchall()
    conn.close()
    return render_template("profil.html", korisnik=korisnik, poruke=poruke)


@app.route("/kviz", methods=["GET", "POST"])
def kviz():
    jmbag = session.get("jmbag")
    if not jmbag:
        return redirect(url_for("registracija"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fakultet, smjer FROM korisnici WHERE jmbag = %s", (jmbag,))
    korisnik = cursor.fetchone()

    if not korisnik:
        return redirect(url_for("registracija"))

    if request.method == "POST":
        rezultat = 0
        odgovori = []

        cursor.execute("SELECT * FROM pitanja WHERE fakultet = %s AND smjer = %s", (korisnik["fakultet"], korisnik["smjer"]))
        pitanja = cursor.fetchall()

        for pitanje in pitanja:
            odg = request.form.get(f"pitanje_{pitanje['id']}")
            tocno = pitanje["tocni_odgovor"].lower()
            if odg:
                ispravno = odg.lower() == tocno
                if ispravno:
                    rezultat += 1
                odgovori.append((pitanje["pitanje"], odg, tocno))

        conn.close()
        return render_template("rezultat_kviz.html", odgovori=odgovori, rezultat=rezultat, ukupno=len(pitanja))

    cursor.execute("SELECT * FROM pitanja WHERE fakultet = %s AND smjer = %s", (korisnik["fakultet"], korisnik["smjer"]))
    pitanja = cursor.fetchall()
    conn.close()
    return render_template("kviz.html", pitanja=pitanja)


@app.route("/troskovi")
def troskovi():
    return render_template("troskovi.html")

@app.route("/api/posao", methods=["POST"])
def preporuci_posao():
    data = request.get_json()
    deficit = float(data.get("deficit", 0))
    jmbag = session.get("jmbag")
    if not jmbag or deficit <= 0:
        return jsonify({"error": "Nema posla za preporuku."})

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT smjer FROM korisnici WHERE jmbag = %s", (jmbag,))
    korisnik = cursor.fetchone()

    if not korisnik:
        conn.close()
        return jsonify({"error": "Korisnik nije pronađen."})

    cursor.execute("SELECT * FROM poslovi WHERE smjer = %s ORDER BY satnica DESC LIMIT 1", (korisnik["smjer"],))
    posao = cursor.fetchone()
    conn.close()

    if not posao:
        return jsonify({"error": "Nema dostupnih poslova za tvoj smjer."})

    sati = deficit / float(posao["satnica"])
    return jsonify({
        "naslov": posao["naslov"],
        "opis": posao["opis"],
        "satnica": float(posao["satnica"]),
        "kontakt": posao["kontakt_email"],
        "deficit": deficit,
        "sati": round(sati, 1)
    })

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
