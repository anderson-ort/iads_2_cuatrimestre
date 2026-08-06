"""
Contrato de datos Pydantic V2 para el sistema de Onboarding de Ortelana Textil.
Reemplaza el parseo cru­do con json.loads() (Clase 2) por un esquema que
coacciona tipos, limpia datos y rechaza estructuralmente lo que no cumple
el contrato, antes de que el dato toque el backend transaccional.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DistribuidorOnboardingSchema(BaseModel):
    """
    Contrato de datos estricto para la normalizacion semantica de mensajes
    de distribuidores que solicitan alta como cliente mayorista de
    Ortelana Textil. Reemplaza el dict suelto que devolvia
    extraer_datos_distribuidor() en 03_clase.md.
    """

    intencion: Literal["ALTA_DISTRIBUIDOR", "CONSULTA_ESTADO", "RECLAMO_CALIDAD"] = (
        Field(
            description="Categoria operativa de la consulta segun el Intent Mapping de la Clase 2."
        )
    )

    cuit: Optional[str] = Field(
        default=None,
        description="CUIT del distribuidor. Debe contener exactamente 11 digitos numericos.",
    )

    razon_social: Optional[str] = Field(
        default=None,
        description="Nombre de la empresa o persona fisica que solicita el alta.",
    )

    responsable: Optional[str] = Field(
        default=None,
        description="Nombre de la persona de contacto / responsable de compras.",
    )

    telefono: Optional[str] = Field(
        default=None, description="Telefono de contacto, en cualquier formato recibido."
    )

    email: Optional[str] = Field(
        default=None, description="Email de contacto del distribuidor."
    )

    rubro: Optional[str] = Field(
        default=None,
        description="Rubro comercial declarado por el distribuidor (ej. indumentaria, calzado).",
    )

    cuit_verificado_externamente: bool = Field(
        default=False,
        description=(
            "SIEMPRE False al salir del LLM. Este campo NUNCA debe ser asignado "
            "por el modelo: solo lo puede poner en True la funcion "
            "verificar_cuit_afip() despues de consultar AFIP. "
            "Es la barrera de diseno contra el Caso de Falla 1 de la Clase 2 "
            "(CUIT verosimil pero inexistente)."
        ),
    )

    # Resolución del Ejercicio: Quinto campo para mitigar Secuestro Semántico
    # categoria_solicitada: Optional[Literal["ESTANDAR", "MINORISTA", "MAYORISTA_VIP"]] = Field(
    #     default="ESTANDAR",
    #     description="Categoria de cliente solicitada o deducida. Filtra intentos de categorias inexistentes (ej: VIP_ORO)."
    # )

    @field_validator("cuit")
    @classmethod
    def limpiar_y_validar_cuit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cuit_limpio = "".join(filter(str.isdigit, v))
        if cuit_limpio and len(cuit_limpio) != 11:
            raise ValueError(
                f"El CUIT debe contener exactamente 11 digitos numericos. "
                f"Recibido: '{v}' -> limpio: '{cuit_limpio}' ({len(cuit_limpio)} digitos)."
            )
        return cuit_limpio

    @field_validator("email")
    @classmethod
    def validar_formato_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError(f"Formato de email invalido: '{v}'")
        return v.strip().lower()

    @field_validator("intencion", mode="before")
    @classmethod
    def normalizar_intencion(cls, v):
        # Defensa contra el Caso de Falla 2 de la Clase 2 (secuestro semantico):
        # si el modelo intenta inventar una intencion fuera del enum
        # (ej. "ALTA_VIP_ORO"), Pydantic la rechaza ANTES de que llegue al backend.
        return v
