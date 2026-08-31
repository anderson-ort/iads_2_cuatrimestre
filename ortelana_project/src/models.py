from pydantic import BaseModel, Field, field_validator

class ExtraccionOnboarding(BaseModel):
    intencion: str = Field(
        description="Tipo de intencion detectada: ALTA_DISTRIBUIDOR, CONSULTA_STOCK, RECLAMO_CALIDAD, OTRA"
    )
    cuit: str | None = Field(
        default=None,
        description="CUIT de la empresa en formato numerico de 11 digitos sin guiones, o null si no esta"
    )
    razon_social: str | None = Field(
        default=None,
        description="Nombre de la empresa o taller mencionado"
    )
    material: str | None = Field(
        default=None,
        description="Nombre de la tela o material consultado"
    )

    # Validacion determinista ejecutada en Python (no en el LLM)
    @field_validator('cuit')
    @classmethod
    def validar_formato_cuit(cls, v: str | None) -> str | None:
        if v is None:
            return None

        cuit_limpio = "".join(filter(str.isdigit, v))

        if len(cuit_limpio) != 11:
            raise ValueError("El CUIT debe tener exactamente 11 digitos numericos")
        return cuit_limpio

class MensajeEntrada(BaseModel):
    texto: str = Field(..., min_length=1, description="Mensaje del distribuidor a procesar")


class RespuestaExtraccion(BaseModel):
    ok: bool
    datos: ExtraccionOnboarding | None = None
    error: str | None = None
