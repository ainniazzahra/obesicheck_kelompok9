"""Aturan edukasi umum berdasarkan kebiasaan yang dilaporkan pengguna."""
SOURCE_DIET = {"label": "WHO — Healthy diet", "url": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet"}
SOURCE_ACTIVITY = {"label": "WHO — Physical activity", "url": "https://www.who.int/news-room/fact-sheets/detail/physical-activity"}
SOURCE_KEMENKES = {"label": "Kementerian Kesehatan RI", "url": "https://www.kemkes.go.id/"}
def recommendations(x: dict) -> list[dict]:
    out=[]
    def add(code,topic,title,reason,steps,source):
        out.append({"code":code,"topic":topic,"title":title,"reason":reason,"steps":steps,"source":source["label"],"source_url":source["url"]})
    if x.get("FAVC")=="yes":
        add("balanced-meals","Pola makan","Bangun pola makan yang lebih seimbang","Anda melaporkan sering mengonsumsi makanan berkalori tinggi. Jawaban ini menjadi pemicu edukasi umum, bukan penilaian bahwa makanan tertentu pasti menyebabkan kondisi tertentu.",["Coba tambahkan sumber serat seperti sayur, buah, kacang-kacangan, atau biji-bijian pada makanan yang biasa dikonsumsi.","Perhatikan porsi dan frekuensi makan secara bertahap tanpa menerapkan diet ekstrem.","Pilih perubahan yang realistis dengan mempertimbangkan anggaran, budaya, dan akses makanan."],SOURCE_DIET)
    if float(x.get("FCVC",2)) < 2.5:
        add("vegetables","Pola makan","Tingkatkan variasi sayur dan buah secara bertahap","Nilai frekuensi konsumsi sayur yang Anda pilih berada pada sisi lebih rendah dari skala dataset.",["Tambahkan satu porsi sayur atau buah pada waktu makan yang paling mudah.","Coba variasi sayuran lokal dan cara memasak yang Anda sukai.","Tingkatkan secara bertahap; tidak perlu mengubah semua kebiasaan sekaligus."],SOURCE_DIET)
    if x.get("CAEC") in ("Frequently","Always"):
        add("snacks","Kebiasaan ngemil","Pilih camilan yang mendukung pola makan seimbang","Anda melaporkan makan di antara waktu makan dengan frekuensi tinggi pada kategori dataset.",["Jika ingin camilan, siapkan pilihan seperti buah, kacang tanpa garam berlebih, atau yoghurt sesuai kebutuhan dan akses.","Perhatikan rasa lapar, jadwal, dan situasi saat ngemil tanpa menghakimi kebiasaan diri.","Hindari melabeli makanan sebagai baik atau buruk secara mutlak; fokus pada pola keseluruhan."],SOURCE_DIET)
    if float(x.get("CH2O",2)) <= 1:
        add("hydration","Kebiasaan minum","Bangun kebiasaan minum secara teratur","Pilihan konsumsi air Anda berada pada kategori rendah dalam skala dataset; skala ini bukan pengukuran volume air klinis.",["Letakkan air minum di tempat yang mudah dijangkau.","Coba minum secara berkala sepanjang hari dan sesuaikan dengan cuaca, aktivitas, serta anjuran tenaga kesehatan.","Jika memiliki pembatasan cairan karena kondisi medis, ikuti arahan tenaga kesehatan."],SOURCE_KEMENKES)
    if float(x.get("FAF",1)) <= 1:
        add("movement","Aktivitas fisik","Mulai dari gerakan ringan yang realistis","Jawaban aktivitas fisik Anda berada pada kategori rendah di skala dataset.",["Pilih aktivitas yang aman dan disukai, misalnya berjalan santai atau peregangan singkat.","Mulai dengan durasi yang nyaman lalu tingkatkan secara bertahap sesuai kemampuan.","Kurangi duduk terlalu lama dengan jeda gerak; jika punya keluhan atau kondisi khusus, konsultasikan pilihan aktivitas."],SOURCE_ACTIVITY)
    if float(x.get("TUE",1)) >= 1.5:
        add("screen-breaks","Rutinitas harian","Selipkan jeda gerak saat menggunakan layar","Nilai penggunaan teknologi yang Anda pilih berada pada kategori relatif tinggi dalam skala dataset.",["Pasang pengingat untuk berdiri atau bergerak ringan secara berkala.","Coba lakukan peregangan sederhana saat jeda belajar atau bekerja.","Jeda gerak merupakan kebiasaan umum; kategori waktu layar saja tidak menentukan status kesehatan."],SOURCE_ACTIVITY)
    if not out:
        add("maintain-habits","Kebiasaan sehat","Pertahankan kebiasaan sehat dan lakukan perubahan kecil","Dari jawaban yang tersedia, tidak ada aturan khusus yang terpenuhi. Materi umum ini tetap bisa menjadi pengingat untuk menjaga pola makan seimbang dan bergerak sesuai kemampuan.",["Pertahankan rutinitas yang terasa nyaman dan berkelanjutan.","Utamakan variasi makanan dan aktivitas fisik yang sesuai kemampuan.","Jika memiliki pertanyaan tentang status kesehatan pribadi, konsultasikan kepada tenaga kesehatan."],SOURCE_DIET)
    return out
