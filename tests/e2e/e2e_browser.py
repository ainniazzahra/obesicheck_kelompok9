"""E2E browser (opsional). Prasyarat: backend di :8000 dan frontend (npm run dev / preview) di :5173, serta `pip install playwright` +
`playwright install chromium`. PERINGATAN: skrip ini mendaftarkan akun uji (prefix `e2e_`) di database backend yang sedang berjalan;
jalankan backend dengan OBESICHECK_DB_PATH khusus uji agar data pengguna tidak tercampur. Jalankan: python tests/e2e/e2e_browser.py"""
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5173")
EXE = os.getenv("CHROMIUM_PATH")  # kosong = browser bawaan Playwright
PW = "Sandi12345"
RUN = str(int(time.time()))[-6:]
OK_BODY = {"id": 1, "history_saved": True, "created_at": "2026-10-20T00:00:00+00:00", "predicted_class": "Obesity_Type_I",
           "probabilities": {"Obesity_Type_I": 0.9, "Normal_Weight": 0.1}, "model_version": "mock", "bmi_indicator": None, "recommendations": [], "disclaimer": "d"}
API_HEALTH = os.getenv("E2E_API_HEALTH", "http://127.0.0.1:8000/api/health")
for _ in range(60):  # tunggu backend siap agar hasil tidak bergantung pada race saat startup
    try:
        urllib.request.urlopen(API_HEALTH, timeout=2).read()  # noqa: S310
        break  # URL tetap http lokal
    except OSError:
        time.sleep(1)
else:
    sys.exit(f"Backend tidak siap di {API_HEALTH}")

out = []
counter = [0]


def rec(name, ok, note=""):
    out.append((name, "PASS" if ok else "FAIL", note))
    print(f"{'PASS' if ok else 'FAIL'} | {name} | {note}")


def uname():
    counter[0] += 1
    return f"e2e_{RUN}_{counter[0]}"


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, args=["--no-sandbox"]) if EXE else p.chromium.launch()

    def new(viewport=None):
        ctx = b.new_context(viewport=viewport or {"width": 1300, "height": 900})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)[:120]))
        pg.on("console", lambda m: errs.append(m.text[:120]) if m.type == "error" and "net::" not in m.text.lower() and "401" not in m.text and "409" not in m.text and "429" not in m.text else None)
        return pg, errs

    def mk(body):
        return lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(body)) if r.request.method == "POST" else r.continue_()

    def signup(pg, name=None, pw=PW):
        name = name or uname()
        pg.goto(BASE); pg.wait_for_timeout(900)
        pg.get_by_role("button", name="Masuk").first.click()
        pg.get_by_role("tab", name="Daftar").click()
        pg.fill("input[name=username]", name); pg.fill("input[name=email]", f"{name}@example.com"); pg.fill("input[name=password]", pw)
        pg.get_by_role("button", name="Daftar dan masuk").click()
        pg.wait_for_selector(".form-card:has-text('Formulir kebiasaan'), .intro-card", timeout=15000)
        return name

    def login_ui(pg, ident, pw=PW):
        pg.goto(BASE); pg.wait_for_timeout(700)
        pg.get_by_role("button", name="Masuk").first.click()
        pg.fill("input[name=identifier]", ident); pg.fill("input[name=password]", pw)
        pg.locator("form button.btn.primary").click()

    def goform(pg):
        pg.get_by_role("button", name="Prediksi Risiko").click()
        pg.wait_for_selector("select")

    def submit(pg): pg.get_by_role("button", name="Lihat hasil estimasi").click()

    def nav(pg, name): pg.get_by_role("button", name=name).first.click(); pg.wait_for_timeout(500)

    # ===== AUTENTIKASI =====
    pg, errs = new(); pg.goto(BASE); pg.wait_for_timeout(1000)
    nav(pg, "Prediksi Risiko")
    rec("A1 halaman privat tanpa login -> formulir masuk + pemberitahuan", pg.locator("input[name=identifier]").count() == 1 and "Masuk atau daftar" in pg.locator("main").inner_text() and pg.locator("select").count() == 0)
    nav(pg, "Riwayat"); rec("A1b riwayat tanpa login -> formulir masuk", pg.locator("input[name=identifier]").count() == 1)
    nav(pg, "Evaluasi Model"); rec("A1c halaman publik (evaluasi) tetap terbuka tanpa login", "Confusion matrix" in pg.locator("main").inner_text())
    pg.get_by_role("button", name="Masuk").first.click(); pg.get_by_role("tab", name="Daftar").click()
    for label, (u, e, pw_, needle) in {"password lemah": ("abc_ok", "a@b.id", "hurufsaja", "huruf serta angka"), "email salah": ("abc_ok", "bukan-email", "Sandi12345", "email"), "username pendek": ("ab", "a@b.id", "Sandi12345", "Username"), "password memuat username": ("tester9", "a@b.id", "tester9Aa1", "username")}.items():
        pg.fill("input[name=username]", u); pg.fill("input[name=email]", e); pg.fill("input[name=password]", pw_); pg.get_by_role("button", name="Daftar dan masuk").click()
        rec(f"A2 validasi registrasi klien: {label}", needle.lower() in pg.locator(".error-msg").inner_text().lower())
    rec("A2e toggle lihat password", pg.get_by_role("button", name="Tampilkan password").count() == 1)
    pg.context.close()

    pg, errs = new(); user_a = signup(pg)
    rec("A3 registrasi -> otomatis masuk, chip pengguna tampil", user_a in pg.locator(".user-chip").inner_text(), user_a)
    nav(pg, "Profil"); t = pg.locator(".profile-card").inner_text()
    rec("A3b profil menampilkan data akun nyata", user_a in t and f"{user_a}@example.com" in t)
    pg.reload(); pg.wait_for_timeout(1500)
    rec("A9 sesi bertahan setelah reload (sessionStorage + /auth/me)", user_a in pg.locator(".user-chip").inner_text())
    rec("A12 tanpa error konsol/halaman pada alur auth", errs == [], str(errs))
    ctx_a = pg  # dipakai lagi di bawah

    pg2, _ = new(); pg2.goto(BASE); pg2.wait_for_timeout(700)
    pg2.get_by_role("button", name="Masuk").first.click(); pg2.get_by_role("tab", name="Daftar").click()
    pg2.fill("input[name=username]", user_a.upper()); pg2.fill("input[name=email]", "lain@example.com"); pg2.fill("input[name=password]", PW)
    pg2.get_by_role("button", name="Daftar dan masuk").click(); pg2.wait_for_timeout(1500)
    rec("A4 username duplikat (beda huruf besar) ditolak", "sudah terdaftar" in pg2.locator(".error-msg").inner_text() and pg2.locator(".user-chip").count() == 0)
    pg2.context.close()

    pg3, _ = new(); login_ui(pg3, user_a, "SalahBanget9"); pg3.wait_for_timeout(1200)
    rec("A5 password salah ditolak, tetap di formulir", "salah" in pg3.locator(".error-msg").inner_text().lower() and pg3.locator(".user-chip").count() == 0)
    pg3.context.close()
    pg3, _ = new(); login_ui(pg3, f"{user_a}@example.com"); pg3.wait_for_selector(".user-chip", timeout=10000)
    rec("A6 login dengan email berhasil", user_a in pg3.locator(".user-chip").inner_text()); pg3.context.close()

    # ===== PREDIKSI, ISOLASI, LOGOUT (akun A) =====
    goform(ctx_a); submit(ctx_a); ctx_a.wait_for_selector(".result-hero h2", timeout=20000)
    rec("S1 prediksi nyata (login) menampilkan hasil + probabilitas", ctx_a.locator(".panel h3", has_text="Probabilitas").count() == 1, ctx_a.locator(".result-hero h2").inner_text())
    nav(ctx_a, "Riwayat"); rec("A8a riwayat akun A berisi 1 entri", ctx_a.locator("tbody tr").count() == 1)
    user_b_pg, _ = new(); user_b = signup(user_b_pg); nav(user_b_pg, "Riwayat")
    rec("A8b akun B tidak melihat riwayat akun A", user_b_pg.locator("tbody tr").count() == 0 and "Belum ada riwayat" in user_b_pg.locator("main").inner_text())
    user_b_pg.context.close()
    for n, exp in [("Beranda", "Langkah kecil"), ("Dashboard", "Ringkasan sistem"), ("Evaluasi Model", "Confusion matrix"), ("Riwayat", "Riwayat estimasi"), ("Profil", "Informasi aplikasi")]:
        nav(ctx_a, n); rec(f"S1b nav {n}", exp.lower() in ctx_a.locator("main").inner_text().lower())
    nav(ctx_a, "Riwayat"); n0 = ctx_a.locator("tbody tr").count(); ctx_a.locator(".icon-button").first.click(); ctx_a.wait_for_timeout(700)
    rec("S8 hapus riwayat milik sendiri", ctx_a.locator("tbody tr").count() == n0 - 1)
    goform(ctx_a); submit(ctx_a); ctx_a.wait_for_selector(".result-hero h2", timeout=20000)
    ctx_a.get_by_role("button", name="Keluar").first.click(); ctx_a.wait_for_timeout(800)
    tok = ctx_a.evaluate("sessionStorage.getItem('obesicheck_token')")
    rec("A7 logout: token dihapus, kembali ke Beranda, chip hilang", tok is None and ctx_a.locator(".user-chip").count() == 0 and "Langkah kecil" in ctx_a.locator("main").inner_text())
    nav(ctx_a, "Prediksi Risiko")
    rec("A7b setelah logout, hasil prediksi lama tidak tampil & halaman privat terkunci", ctx_a.locator(".result-hero").count() == 0 and ctx_a.locator("input[name=identifier]").count() == 1)
    ctx_a.fill("input[name=identifier]", user_a); ctx_a.fill("input[name=password]", PW); ctx_a.locator("form button.btn.primary").click(); ctx_a.wait_for_selector(".user-chip", timeout=10000)
    nav(ctx_a, "Riwayat"); rec("A7c login ulang: riwayat akun tetap ada, tidak ada hasil lama", ctx_a.locator(".result-hero").count() == 0 and ctx_a.locator("tbody tr").count() >= 1)
    ctx_a.context.close()

    # sesi dicabut server-side saat browser masih memegang token
    pg, errs = new(); u = signup(pg)
    pg.evaluate("fetch('http://127.0.0.1:8000/api/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+sessionStorage.getItem('obesicheck_token')}})"); pg.wait_for_timeout(500)
    nav(pg, "Riwayat"); pg.get_by_role("button", name="Muat ulang").click(); pg.wait_for_timeout(1200)
    rec("A10 token dicabut -> UI kembali ke formulir masuk dengan pesan sesi berakhir", pg.locator("input[name=identifier]").count() == 1 and "Sesi Anda berakhir" in pg.locator("main").inner_text() and pg.locator(".user-chip").count() == 0)
    pg.context.close()

    # lockout brute force
    pg, _ = new(); u = signup(pg); pg.evaluate("sessionStorage.clear()"); pg.goto(BASE); pg.wait_for_timeout(600)
    pg.get_by_role("button", name="Masuk").first.click()
    for _ in range(5):
        pg.fill("input[name=identifier]", u); pg.fill("input[name=password]", "SalahBanget9"); pg.locator("form button.btn.primary").click(); pg.wait_for_timeout(500)
    pg.fill("input[name=password]", PW); pg.locator("form button.btn.primary").click(); pg.wait_for_timeout(800)
    rec("A11 lockout setelah 5 percobaan gagal (password benar pun ditolak)", "Terlalu banyak" in pg.locator(".error-msg").inner_text() and pg.locator(".user-chip").count() == 0)
    pg.context.close()

    # ===== KONTRAK & KONDISI GAGAL (login dulu, lalu mock) =====
    pg, errs = new(); signup(pg); goform(pg); submit(pg); pg.wait_for_selector(".result-hero h2", timeout=20000)
    rec("S1d tanpa error konsol pada alur prediksi", errs == [], str(errs)); pg.context.close()

    pg, errs = new(); signup(pg); pg.route("**/api/**", lambda r: r.abort()); goform(pg); submit(pg); pg.wait_for_timeout(800)
    txt = pg.locator(".error-msg").inner_text() if pg.locator(".error-msg").count() else ""
    rec("S2 backend mati -> error jelas, tanpa halaman hasil", "Tidak dapat terhubung" in txt and pg.locator(".result-hero").count() == 0, txt[:70])
    rec("S2b pengguna tetap login saat backend sementara mati (bukan dikeluarkan)", pg.locator(".user-chip").count() == 1); pg.context.close()

    pg, errs = new(); signup(pg)
    pg.route("**/api/predictions", lambda r: r.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "Model belum dilatih."})) if r.request.method == "POST" else r.continue_())
    goform(pg); submit(pg); pg.wait_for_timeout(800)
    rec("S3 503 -> pesan tampil, tanpa hasil", "Model belum dilatih" in pg.locator(".error-msg").inner_text() and pg.locator(".result-hero").count() == 0); pg.context.close()

    pg, errs = new(); signup(pg)
    pg.route("**/api/predictions", lambda r: r.fulfill(status=422, content_type="application/json", body=json.dumps({"detail": [{"loc": ["body", "Age"], "msg": "Input should be >= 14"}]})) if r.request.method == "POST" else r.continue_())
    goform(pg); submit(pg); pg.wait_for_timeout(600)
    rec("S4 422 diformat", "Age: Input should be >= 14" in pg.locator(".error-msg").inner_text()); pg.context.close()

    for label, body in [("objek kosong {}", {}), ("tanpa probabilities", {"predicted_class": "Normal_Weight"}), ("kelas tak dikenal", {**OK_BODY, "predicted_class": "Alien"}),
                        ("steps rekomendasi hilang", {**OK_BODY, "recommendations": [{"code": "x", "topic": "t", "title": "t", "reason": "r", "source": "s", "source_url": "https://x"}]})]:
        pg, errs = new(); signup(pg); pg.route("**/api/predictions", mk(body)); goform(pg); submit(pg); pg.wait_for_timeout(700)
        shown = pg.locator(".result-hero").count() > 0; err = pg.locator(".error-msg").count() > 0; blank = pg.locator("#root").inner_text().strip() == ""
        rec(f"S5 kontrak rusak: {label} -> ditolak dengan error", err and not shown and not blank, f"shown={shown} err={err} blank={blank}"); pg.context.close()

    pg, errs = new(); signup(pg); goform(pg); submit(pg); pg.wait_for_selector(".result-hero h2", timeout=20000)
    pg.route("**/api/predictions", lambda r: r.abort() if r.request.method == "POST" else r.continue_())
    pg.get_by_role("button", name="Buat estimasi baru").click(); submit(pg); pg.wait_for_timeout(700)
    rec("S6 gagal setelah sukses: hasil lama tidak tampil", pg.locator(".result-hero").count() == 0 and pg.locator(".error-msg").count() == 1); pg.context.close()

    pg, errs = new(); signup(pg); calls = []

    def slow(r):
        if r.request.method == "POST":
            calls.append(1); pg.wait_for_timeout(1500); r.fulfill(status=200, content_type="application/json", body=json.dumps(OK_BODY))
        else:
            r.continue_()
    pg.route("**/api/predictions", slow); goform(pg); submit(pg); pg.wait_for_timeout(200)
    rec("S7 loading menonaktifkan tombol", pg.get_by_role("button", name="Memproses").count() == 1 and pg.get_by_role("button", name="Memproses").is_disabled())
    pg.wait_for_selector(".result-hero", timeout=8000); rec("S7b tepat satu request", len(calls) == 1, str(len(calls))); pg.context.close()

    pg, errs = new(); signup(pg); goform(pg); a = pg.locator("input[type=number]").first; a.fill(""); submit(pg)
    rec("S11 Age kosong diblokir", "wajib" in pg.locator(".error-msg").inner_text().lower())
    a.fill("150"); submit(pg); rec("S11b Age 150 diblokir", "rentang" in pg.locator(".error-msg").inner_text().lower())
    a.fill("30"); pg.locator("input[type=number]").nth(1).fill("1.7"); submit(pg); rec("S12 Height tanpa Weight diblokir", "bersamaan" in pg.locator(".error-msg").inner_text().lower()); pg.context.close()

    for w in (375, 768):
        pg, errs = new({"width": w, "height": 800}); pg.goto(BASE); pg.wait_for_timeout(900)
        rec(f"S10a tombol navigasi punya nama aksesibel {w}px", pg.get_by_role("button", name="Beranda").count() >= 1 and pg.get_by_role("button", name="Masuk").count() >= 1)
        for idx, n in ((0, "Beranda"), (2, "Prediksi Risiko (login)"), (3, "Evaluasi Model")):
            pg.locator(".nav-item").nth(idx).click(); pg.wait_for_timeout(300)
            rec(f"S10 tanpa overflow horizontal {w}px {n}", not pg.evaluate("document.documentElement.scrollWidth>window.innerWidth+1"))
        pg.screenshot(path=f"e2e_mobile_{w}.png"); pg.context.close()
    b.close()

fails = sum(1 for o in out if o[1] == "FAIL")
print("\nSUMMARY", sum(1 for o in out if o[1] == "PASS"), "pass", fails, "fail")
sys.exit(1 if fails else 0)
