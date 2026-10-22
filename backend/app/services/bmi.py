"""Indikator BMI terpisah dari model ML (rumus baku, bukan keluaran model)."""

def bmi_info(height_m: float | None, weight_kg: float | None, age: float) -> dict | None:
    if height_m is None or weight_kg is None:
        return None
    bmi = round(weight_kg / height_m ** 2, 1)
    info = {"bmi": bmi, "source": "Rumus BMI = berat (kg) / tinggi (m)^2; bukan keluaran model ML."}
    if age >= 18:  # ambang WHO untuk dewasa
        cat = ("Berat badan kurang" if bmi < 18.5 else "Normal" if bmi < 25 else "Kelebihan berat badan (pre-obesitas)" if bmi < 30
               else "Obesitas kelas I" if bmi < 35 else "Obesitas kelas II" if bmi < 40 else "Obesitas kelas III")
        info["who_adult_category"] = cat
    else:
        info["note"] = "Usia < 18 tahun: interpretasi BMI memerlukan kurva BMI-menurut-umur; kategori dewasa tidak ditampilkan."
    return info
