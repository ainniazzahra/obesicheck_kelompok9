from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictionInput(BaseModel):
    """Input prediksi. Field model = 14 fitur hasil training (tanpa Height/Weight).

    Height/Weight bersifat OPSIONAL dan TIDAK dikirim ke model: hanya dipakai untuk menghitung
    indikator BMI terpisah, karena label dataset didefinisikan dari BMI (kebocoran label bila dipakai sebagai fitur).
    """
    model_config = ConfigDict(extra="forbid")

    Gender: Literal["Female", "Male"]
    Age: float = Field(ge=14, le=100, strict=True)
    family_history_with_overweight: Literal["yes", "no"]
    FAVC: Literal["yes", "no"]
    FCVC: float = Field(ge=1, le=3, strict=True)
    NCP: float = Field(ge=1, le=4, strict=True)
    CAEC: Literal["no", "Sometimes", "Frequently", "Always"]
    SMOKE: Literal["no", "yes"]
    CH2O: float = Field(ge=1, le=3, strict=True)
    SCC: Literal["no", "yes"]
    FAF: float = Field(ge=0, le=3, strict=True)
    TUE: float = Field(ge=0, le=2, strict=True)
    CALC: Literal["no", "Sometimes", "Frequently", "Always"]
    MTRANS: Literal["Public_Transportation", "Automobile", "Walking", "Motorbike", "Bike"]
    Height: float | None = Field(default=None, ge=1.2, le=2.3, strict=True, description="Meter. Opsional; hanya untuk indikator BMI.")
    Weight: float | None = Field(default=None, ge=25, le=300, strict=True, description="Kg. Opsional; hanya untuk indikator BMI.")

    @model_validator(mode="after")
    def height_weight_together(self):
        if (self.Height is None) != (self.Weight is None):
            raise ValueError("Height dan Weight harus diisi bersamaan atau dikosongkan keduanya.")
        return self


MODEL_FIELDS = [f for f in PredictionInput.model_fields if f not in ("Height", "Weight")]
