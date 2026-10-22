from app.services.bmi import bmi_info


def test_bmi_adult_category():
    assert bmi_info(1.7, 72.25, 30)["who_adult_category"].startswith("Kelebihan")  # BMI 25.0
    assert bmi_info(1.7, 60, 30)["who_adult_category"] == "Normal"
    assert bmi_info(1.6, 100, 30)["who_adult_category"] == "Obesitas kelas II"


def test_bmi_minor_and_missing():
    assert "who_adult_category" not in bmi_info(1.6, 50, 16)
    assert bmi_info(None, 50, 30) is None
